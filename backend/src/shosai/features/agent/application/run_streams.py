"""A run's stream as the API serves it: open, resumed, or stopped (ADR 0032; agent plan §3.5).

Only the run's person reads or stops it (404 `run_not_found` for anyone else). A stream
follows the run's log from the number the client saw; a log gone (an hour after its last
write, ten minutes after the run's end) is 410
`run_events_gone`, and the client reloads the thread. When a run's log stays silent for 45 s,
its record is read: a run that ended there — its worker committed the end but could not write
it to the log — ends the stream with the event its record holds, so no client waits for an
end that already happened. "Stop" is a request the run's worker reads within half a second;
asking again, or after the end, changes nothing.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime, timedelta
from http import HTTPStatus
from uuid import UUID

from sqlalchemy import select

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.errors import AppError
from shosai.core.kv.connection import REDIS_FAILURES
from shosai.features.agent.domain.endings import paused, recorded
from shosai.features.agent.domain.runs import STREAM_STALL, RunStatus
from shosai.features.agent.domain.stream import StreamEvent
from shosai.features.agent.domain.threads import MessageRole
from shosai.features.agent.infrastructure.log_tail import LogTail, Silence
from shosai.features.agent.infrastructure.run_log import RunLog
from shosai.features.agent.infrastructure.run_metrics import RunMetrics
from shosai.features.agent.infrastructure.run_records import AgentActionRecord, AgentRunRecord
from shosai.features.agent.infrastructure.thread_lease import ThreadLeases
from shosai.features.agent.infrastructure.thread_records import AgentMessageRecord
from shosai.features.identity.contracts import Principal

RUN = AgentRunRecord


@dataclass(frozen=True, slots=True)
class RunRecord:
    """What the API reads of a run."""

    run_id: UUID
    started_at: datetime
    thread_id: UUID
    status: RunStatus
    code: str | None


def unavailable() -> AppError:
    """Valkey did not answer."""
    return AppError("agent_unavailable", HTTPStatus.SERVICE_UNAVAILABLE)


class RunStreams:
    """Serves and stops the person's runs."""

    def __init__(
        self,
        transactions: HomeTransactions,
        logs: tuple[RunLog, LogTail],
        leases: ThreadLeases,
        metrics: RunMetrics,
        silence: timedelta = STREAM_STALL,
    ) -> None:
        self._transactions = transactions
        self._log, self._tail = logs
        self._leases = leases
        self._metrics = metrics
        self._silence = silence

    async def owned(self, principal: Principal, run_id: UUID) -> RunRecord:
        """The person's run; `run_not_found` for any other."""
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            row = (
                await session.execute(
                    select(RUN.id, RUN.started_at, RUN.thread_id, RUN.status, RUN.outcome_code)
                    .where(RUN.id == run_id, RUN.user_id == principal.user_id)
                    .limit(1)
                )
            ).one_or_none()
        if row is None:
            raise AppError("run_not_found", HTTPStatus.NOT_FOUND)
        return RunRecord(row[0], row[1], row[2], RunStatus(row[3]), row[4])

    async def resumable(self, principal: Principal, run_id: UUID) -> RunRecord:
        """The person's run whose log is still kept; 410 `run_events_gone` once it is gone."""
        run = await self.owned(principal, run_id)
        try:
            kept = await self._log.kept(run_id)
        except REDIS_FAILURES as error:
            raise unavailable() from error
        if not kept:
            self._metrics.resumed("gone")
            raise AppError("run_events_gone", HTTPStatus.GONE)
        self._metrics.resumed("served")
        return run

    def events(self, principal: Principal, run_id: UUID, after: int) -> AsyncIterator[StreamEvent]:
        """The run's events after number `after`, to its one terminal event."""
        silence = Silence(self._silence, lambda seq: self._ended(principal, run_id, seq))
        return self._tail.follow(run_id, after, silence)

    async def stop(self, principal: Principal, run_id: UUID) -> None:
        """Ask the person's run to stop."""
        await self.owned(principal, run_id)
        try:
            await self._leases.ask_to_stop(run_id)
        except REDIS_FAILURES as error:
            raise unavailable() from error

    async def _ended(self, principal: Principal, run_id: UUID, seq: int) -> StreamEvent | None:
        run = await self.owned(principal, run_id)
        if run.status is RunStatus.PAUSED:
            action_id = await self._awaited(principal, run)
            if action_id is None:
                return None
            return StreamEvent(seq + 1, *paused(action_id).terminal(None))
        ending = recorded(run.status, run.code)
        if ending is None:
            return None
        kind, data = ending.terminal(await self._answer_id(principal, run))
        return StreamEvent(seq + 1, kind, data)

    async def _awaited(self, principal: Principal, run: RunRecord) -> UUID | None:
        """The action a paused run waits for."""
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            return await session.scalar(
                select(AgentActionRecord.id)
                .where(AgentActionRecord.run_id == run.run_id)
                .order_by(AgentActionRecord.created_at.desc())
                .limit(1)
            )

    async def _answer_id(self, principal: Principal, run: RunRecord) -> UUID | None:
        message = AgentMessageRecord
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            return await session.scalar(
                select(message.id).where(
                    message.thread_id == run.thread_id,
                    message.run_id == run.run_id,
                    message.role == MessageRole.ASSISTANT.value,
                    message.created_at >= run.started_at,
                )
            )
