"""The runs an agent worker drives, kept alive together (Leo §12, ADR 0068 AG-D12).

One task per process watches every run it drives: twice a second it reads their stop requests
in one round trip, and every 10 s it renews their threads' leases and their counts in the
fleet. A stop request cancels the run's work, which then ends `stopped` with its text; a run
whose lease is no longer its own — the sweep found it lost — is cancelled too and writes
nothing more. A failing Valkey is logged and the runs go on to their own deadline. The task
starts with the process's first run and ends with the process.
"""

import asyncio
import time
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Final
from uuid import UUID

import structlog

from shosai.core.kv.connection import REDIS_FAILURES
from shosai.features.agent.domain.runs import LEASE_RENEWAL
from shosai.features.agent.infrastructure.fleet import Fleet
from shosai.features.agent.infrastructure.thread_lease import ThreadLeases

WATCH_EVERY: Final = timedelta(milliseconds=500)
log = structlog.stdlib.get_logger(__name__)


@dataclass(eq=False)
class ActiveRun:
    """A run this worker drives: its ids, its work, and whether it was stopped or lost."""

    run_id: UUID
    thread_id: UUID
    user_id: UUID
    work: asyncio.Task[Any] | None = None
    stop_asked: bool = False
    lost: bool = False

    def stop(self) -> None:
        """The person asked the run to stop."""
        if not (self.stop_asked or self.lost):
            self.stop_asked = True
            self._cancel()

    def lose(self) -> None:
        """Another took the run's lease: it must write nothing more."""
        if not self.lost:
            self.lost = True
            self._cancel()

    def _cancel(self) -> None:
        if self.work is not None and not self.work.done():
            self.work.cancel()


class RunRegistry:
    """The process's active runs and the one task that keeps them alive."""

    def __init__(
        self,
        leases: ThreadLeases,
        fleet: Fleet,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._leases = leases
        self._fleet = fleet
        self._clock = clock
        self._runs: dict[UUID, ActiveRun] = {}
        self._renewed = clock()
        self._watcher: asyncio.Task[None] | None = None

    def join(self, run: ActiveRun) -> None:
        """Watch a run from now on."""
        self._runs[run.run_id] = run
        if self._watcher is None or self._watcher.done():
            self._watcher = asyncio.create_task(self._watch_forever(), name="agent-runs-watch")

    def leave(self, run: ActiveRun) -> None:
        """Stop watching a run that ended."""
        self._runs.pop(run.run_id, None)

    @property
    def count(self) -> int:
        """How many runs this worker drives now."""
        return len(self._runs)

    async def close(self) -> None:
        """Stop the watcher; called when the process stops."""
        if self._watcher is not None:
            self._watcher.cancel()
            with suppress(asyncio.CancelledError):
                await self._watcher

    async def watch_once(self) -> None:
        """Read the stop requests and, when due, renew the leases and the counts."""
        runs = list(self._runs.values())
        if not runs:
            return
        for run_id in await self._leases.stops_asked([run.run_id for run in runs]):
            asked = self._runs.get(run_id)
            if asked is not None:
                asked.stop()
        now = self._clock()
        if now - self._renewed < LEASE_RENEWAL.total_seconds():
            return
        self._renewed = now
        lost = await self._leases.renew([(run.thread_id, run.run_id) for run in runs])
        await self._fleet.renew([(run.user_id, run.run_id) for run in runs])
        for run in runs:
            if run.run_id in lost:
                log.warning("Ход Leo потерял аренду треда", run_id=str(run.run_id))
                run.lose()

    async def _watch_forever(self) -> None:
        while True:
            await asyncio.sleep(WATCH_EVERY.total_seconds())
            try:
                await self.watch_once()
            except REDIS_FAILURES as error:
                log.warning(
                    "Valkey не ответил наблюдателю ходов Leo", error_type=type(error).__name__
                )
