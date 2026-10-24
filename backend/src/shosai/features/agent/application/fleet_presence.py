"""An agent worker's place in the fleet's capacity (Leo §12, ADR 0068 AG-D12).

Beside the `agent` queue's worker, the process says every 10 s that it is alive and can take
48 runs; when it stops taking runs — the start of a release's drain — it leaves the capacity
at once, while the runs it holds go on to their end. A failing Valkey is logged; a worker
that stopped saying it is alive leaves the capacity in 30 s.
"""

import asyncio
import os
import secrets
import socket
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from datetime import timedelta
from typing import Final

import structlog

from shosai.core.kv.connection import REDIS_FAILURES
from shosai.features.agent.domain.runs import LEASE_RENEWAL
from shosai.features.agent.infrastructure.fleet import Fleet

BEAT: Final = LEASE_RENEWAL
log = structlog.stdlib.get_logger(__name__)


def worker_name() -> str:
    """This process among the fleet's workers: host, process id and a random part."""
    return f"{socket.gethostname()}-{os.getpid()}-{secrets.token_hex(4)}"


@asynccontextmanager
async def present_in_fleet(fleet: Fleet, beat: timedelta = BEAT) -> AsyncIterator[None]:
    """Count this worker in the fleet's capacity while the block runs."""
    worker = worker_name()

    async def keep_present() -> None:
        while True:
            try:
                await fleet.alive(worker)
            except REDIS_FAILURES as error:
                log.warning(
                    "Воркер ходов Leo не отметился в парке", error_type=type(error).__name__
                )
            await asyncio.sleep(beat.total_seconds())

    task = asyncio.create_task(keep_present(), name="agent-fleet-presence")
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        try:
            await fleet.gone(worker)
        except REDIS_FAILURES as error:
            log.warning("Воркер ходов Leo не вышел из парка", error_type=type(error).__name__)
