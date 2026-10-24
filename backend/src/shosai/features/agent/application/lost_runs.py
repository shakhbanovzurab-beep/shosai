"""Runs whose worker was lost, ended within a minute (Leo §12; agent plan §3.5 flow 4, AG-D12).

A minute's tick lists, as the sweep role, the runs still `running` that started more than
30 s ago; a run whose thread lease is no longer its own has no worker behind it — its worker
died, or it never reached one. Each is ended `failed` with `process_lost` in its person's
transaction, with the same condition the worker's end uses, so of the two exactly one records
the end; the winner writes `run.failed` after the log's last event and gives back the run's
count. The queue never runs it again: the question is kept, and "Retry" answers it.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Final
from uuid import UUID

import structlog
from sqlalchemy import select, update

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.kv.connection import REDIS_FAILURES
from shosai.features.agent.domain.endings import failed
from shosai.features.agent.domain.runs import LEASE_TTL, Channel, RunFailure, RunStatus
from shosai.features.agent.domain.stream import StreamEvent
from shosai.features.agent.infrastructure.fleet import Fleet
from shosai.features.agent.infrastructure.run_log import RunLog
from shosai.features.agent.infrastructure.run_metrics import RunMetrics
from shosai.features.agent.infrastructure.run_records import AgentRunRecord
from shosai.features.agent.infrastructure.thread_lease import ThreadLeases

RUN = AgentRunRecord
BATCH: Final = 200
log = structlog.stdlib.get_logger(__name__)


class LostRuns:
    """The minute's sweep of runs without a worker."""

    def __init__(
        self,
        transactions: HomeTransactions,
        valkey_parts: tuple[RunLog, ThreadLeases, Fleet],
        metrics: RunMetrics,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._log, self._leases, self._fleet = valkey_parts
        self._metrics = metrics
        self._clock = clock

    async def sweep(self, home: Home) -> int:
        """End the home's lost runs; how many were ended."""
        now = self._clock()
        due = (
            select(RUN.id, RUN.started_at, RUN.thread_id, RUN.user_id)
            .where(RUN.status == RunStatus.RUNNING.value, RUN.started_at < now - LEASE_TTL)
            .order_by(RUN.started_at)
            .limit(BATCH)
        )
        async with self._transactions.begin(
            TenancyScope(home), read_only=True, sweep=True
        ) as session:
            rows = (await session.execute(due)).all()
        ended = 0
        for run_id, started_at, thread_id, user_id in rows:
            if await self._leases.holder(thread_id) == run_id:
                continue
            if await self._end(TenancyScope(home, user_id), (run_id, started_at), now):
                ended += 1
                self._metrics.ended(Channel.WEB, RunFailure.PROCESS_LOST.value)
                await self._close_log(run_id)
                await self._fleet.release(user_id, run_id)
        if ended:
            log.warning("Потерянные ходы Leo завершены", home=home.value, runs=ended)
        return ended

    async def _end(self, scope: TenancyScope, run: tuple[UUID, datetime], now: datetime) -> bool:
        run_id, started_at = run
        async with self._transactions.begin(scope) as session:
            won = await session.scalar(
                update(RUN)
                .where(
                    RUN.id == run_id,
                    RUN.started_at == started_at,
                    RUN.status == RunStatus.RUNNING.value,
                )
                .values(
                    status=RunStatus.FAILED.value,
                    outcome_code=RunFailure.PROCESS_LOST.value,
                    ended_at=now,
                )
                .returning(RUN.id)
            )
        return won is not None

    async def _close_log(self, run_id: UUID) -> None:
        kind, data = failed(RunFailure.PROCESS_LOST).terminal(None)
        try:
            last = await self._log.last(run_id)
            await self._log.append(
                run_id, (StreamEvent((last.seq if last else 0) + 1, kind, data),)
            )
        except REDIS_FAILURES as error:
            # Поток клиента возьмёт конец из записи хода после 45 с тишины.
            log.warning("Конец потерянного хода не попал в журнал", error_type=type(error).__name__)
