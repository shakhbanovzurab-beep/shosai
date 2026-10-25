"""A paused run closed without its epilogue (Leo §5.3 step 4; agent step 9a).

A run whose card ended without an approval, or whose resume cannot happen — its frame is
gone, or a new turn took the thread — closes `completed` with the reason it had no epilogue.
The close is one conditional update of a run still `paused`, so of two closers one writes it;
it tells the after-turn work through the outbox and, after the commit, ends the run's log for
a cabinet still following and deletes the run's frame. A new turn closes its thread's paused
runs in its own first transaction: their cards stay decidable, and a decision then only adds
its server note.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.kv.connection import REDIS_FAILURES
from shosai.features.agent.application.run_resumption import ResumePayload
from shosai.features.agent.application.turn_task import RunEmitter
from shosai.features.agent.contracts.events import TurnCompleted
from shosai.features.agent.domain.endings import closed
from shosai.features.agent.domain.runs import CloseReason, RunStatus
from shosai.features.agent.infrastructure.run_log import RunLog
from shosai.features.agent.infrastructure.run_records import AgentRunRecord
from shosai.features.agent.infrastructure.thread_records import AgentThreadRecord
from shosai.features.agent.infrastructure.turn_saver import TurnSaver

RUN = AgentRunRecord
log = structlog.stdlib.get_logger(__name__)


async def close_for_new_turn(session: AsyncSession, thread_id: UUID, now: datetime) -> list[UUID]:
    """In a new turn's first transaction: the thread's paused runs end; their ids."""
    closed_runs = await session.scalars(
        update(RUN)
        .where(RUN.thread_id == thread_id, RUN.status == RunStatus.PAUSED.value)
        .values(
            status=RunStatus.COMPLETED.value, outcome_code=CloseReason.NEW_TURN.value, ended_at=now
        )
        .returning(RUN.id)
    )
    return list(closed_runs)


class RunCloser:
    """Closes paused runs that get no epilogue."""

    def __init__(
        self,
        writers: tuple[HomeTransactions, EventOutbox],
        keys: tuple[RunLog, TurnSaver],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions, self._outbox = writers
        self._log, self._frames = keys
        self._clock = clock

    async def close(
        self, session: AsyncSession, run: tuple[UUID, AgentThreadRecord], reason: CloseReason
    ) -> bool:
        """In the caller's transaction: close the run if still paused; whether this closed it."""
        run_id, thread = run
        won = await session.scalar(
            update(RUN)
            .where(RUN.id == run_id, RUN.status == RunStatus.PAUSED.value)
            .values(
                status=RunStatus.COMPLETED.value, outcome_code=reason.value, ended_at=self._clock()
            )
            .returning(RUN.id)
        )
        if won is None:
            return False
        completed = TurnCompleted(thread_id=thread.id, run_id=run_id, user_id=thread.user_id)
        await self._outbox.add(session, completed)
        return True

    async def lose(self, resume: ResumePayload) -> None:
        """A resume that cannot happen: the run closes without its epilogue, its log ends."""
        scope = TenancyScope(resume.home, resume.user_id)
        async with self._transactions.begin(scope) as session:
            thread = await session.scalar(
                select(AgentThreadRecord).where(AgentThreadRecord.id == resume.thread_id)
            )
            won = thread is not None and await self.close(
                session, (resume.run_id, thread), CloseReason.CHECKPOINT_LOST
            )
        if won:
            await self.ended(resume.run_id, CloseReason.CHECKPOINT_LOST)
        else:
            await self._frames.forget(resume.run_id)

    async def ended(self, run_id: UUID, reason: CloseReason, note_id: UUID | None = None) -> None:
        """After the commit: the run's end on its log — a log gone with its hour stays gone —
        and its frame deleted."""
        await self._frames.forget(run_id)
        try:
            last = await self._log.last(run_id)
            if last is not None:
                emitter = RunEmitter(self._log, run_id, after=last.seq)
                await emitter.emit(*closed(reason).terminal(note_id))
        except REDIS_FAILURES as error:
            # Конец записан в базе: кабинет возьмёт его из истории.
            log.warning("Конец прогона Leo не попал в журнал", error_type=type(error).__name__)
