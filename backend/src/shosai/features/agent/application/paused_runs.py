"""A paused run once its card is decided: its epilogue, or its close (Leo §5.3; steps 9a1, 9a2).

Whatever the person decides — approve, reject, or let the card expire — the action lives in
the database and ends there, and a server note joins the thread in the same transaction — for
a card a slice put there without a run too: the person's history shows the card's end, and
Leo reads what happened in plain words. An action
that ended after an approval hands its paused run to the `agent` queue, which resumes the
frame for the epilogue; a rejected or expired card closes the run `completed` (`decided`), and
so does a hand-over that cannot be sent (`checkpoint_lost`). A run a new turn closed already is
left as it is, its card still decidable. The run's log, kept while the card waited, carries
`action.updated` and then the epilogue or `run.completed` to a cabinet still following.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final, Protocol
from uuid import UUID

import structlog
from pydantic import JsonValue
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.homes import Home
from shosai.core.kernel.ids import new_id
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.kv.connection import REDIS_FAILURES
from shosai.core.tasks.declaration import TaskDeclaration
from shosai.core.tasks.errors import TaskQueueUnavailableError
from shosai.features.agent.application.action_cards import ActionCards
from shosai.features.agent.application.action_rows import items_of
from shosai.features.agent.application.run_close import RunCloser
from shosai.features.agent.application.run_resumption import RESUME_RUN, ResumePayload
from shosai.features.agent.application.turn_task import RunEmitter
from shosai.features.agent.domain.actions import ActionStatus
from shosai.features.agent.domain.runs import CloseReason, RunStatus
from shosai.features.agent.domain.stream import EventKind
from shosai.features.agent.domain.threads import MessageRole
from shosai.features.agent.infrastructure.prompts import ACTION_NOTE, ACTION_OUTCOMES
from shosai.features.agent.infrastructure.run_log import RunLog
from shosai.features.agent.infrastructure.run_records import AgentActionRecord, AgentRunRecord
from shosai.features.agent.infrastructure.thread_records import (
    AgentMessageRecord,
    AgentThreadRecord,
)
from shosai.features.agent.infrastructure.turn_saver import TurnSaver

RUN = AgentRunRecord
NO_CODE: Final = "unknown"
# Концы действия после одобрения: его прогон пишет эпилог, если кадр жив.
AFTER_APPROVAL: Final = frozenset(
    {
        ActionStatus.SUCCEEDED,
        ActionStatus.PARTIALLY_SUCCEEDED,
        ActionStatus.FAILED,
        ActionStatus.OUTCOME_UNKNOWN,
    }
)
log = structlog.stdlib.get_logger(__name__)


class ResumeQueue(Protocol):
    """Hands a paused run to the `agent` queue for its epilogue."""

    async def send(self, task: TaskDeclaration[ResumePayload], payload: ResumePayload) -> str:
        """Queue the resume; its task id."""
        ...


@dataclass(frozen=True, slots=True)
class Settled:
    """What a decided action did to its run: the note it added, and whether the run closed
    now or waits for its epilogue."""

    note_id: UUID | None = None
    closed: bool = False
    resumes: bool = False


def action_note(record: AgentActionRecord) -> str:
    """What Leo reads of the decided action: English, registered."""
    items = items_of(record)
    code = next((item.code for item in items if item.code), None) or NO_CODE
    outcome = ACTION_OUTCOMES[record.status].format(code=code)
    return ACTION_NOTE.format(tool=items[0].tool, outcome=outcome)


def resumable(record: AgentActionRecord) -> bool:
    """Whether the action ended after the person approved it."""
    return record.approved_at is not None and ActionStatus(record.status) in AFTER_APPROVAL


class PausedRuns:
    """Settles the run a decided action paused, and tells its cabinet."""

    def __init__(
        self,
        writers: tuple[HomeTransactions, EventOutbox],
        keys: tuple[RunLog, TurnSaver],
        parts: tuple[ResumeQueue, ActionCards],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions, self._log = writers[0], keys[0]
        self._closer = RunCloser(writers, keys, clock)
        self._queue, self._cards = parts
        self._clock = clock

    @property
    def closer(self) -> RunCloser:
        """What closes the runs that get no epilogue."""
        return self._closer

    async def settle(self, session: AsyncSession, record: AgentActionRecord) -> Settled:
        """In the decider's transaction: the note, then the run left for its epilogue or
        closed."""
        if record.thread_id is None:
            return Settled()
        thread = await session.scalar(
            select(AgentThreadRecord).where(AgentThreadRecord.id == record.thread_id)
        )
        if thread is None:
            return Settled()
        now = self._clock()
        note_id = new_id()
        session.add(
            AgentMessageRecord(
                id=note_id, created_at=now, thread_id=thread.id, user_id=thread.user_id,
                run_id=record.run_id, role=MessageRole.SERVER.value, text="",
                action_ids=[record.id], digest={"text": action_note(record)},
            )
        )  # fmt: skip
        thread.last_activity_at = now
        if record.run_id is None:
            # Карточку положил срез без хода (AG-R2): прогона нет, заметка — его конец.
            return Settled(note_id)
        if resumable(record):
            paused = await session.scalar(
                select(RUN.id).where(RUN.id == record.run_id, RUN.status == RunStatus.PAUSED.value)
            )
            return Settled(note_id, resumes=paused is not None)
        closed = await self._closer.close(session, (record.run_id, thread), CloseReason.DECIDED)
        return Settled(note_id, closed=closed)

    async def tell(
        self,
        home: Home,
        record: AgentActionRecord,
        settled: Settled | None = None,
        invalidates: tuple[str, ...] = (),
    ) -> None:
        """After the commit: the card's new state on the run's log, then its run's end or its
        hand-over for the epilogue. A log gone with its hour is left gone: the cabinet reloads."""
        if record.run_id is None:
            return
        scope = TenancyScope(home, record.user_id)
        async with self._transactions.begin(scope, read_only=True) as session:
            (card,) = await self._cards.cards(session, [record])
        try:
            last = await self._log.last(record.run_id)
            if last is not None:
                updated: dict[str, JsonValue] = {"action": card}
                if invalidates:
                    updated["invalidates"] = list(invalidates)
                emitter = RunEmitter(self._log, record.run_id, after=last.seq)
                await emitter.emit(EventKind.ACTION_UPDATED, updated)
        except REDIS_FAILURES as error:
            # Решение записано в базе: кабинет возьмёт его из истории и карточки.
            log.warning("Решение по карточке не попало в журнал", error_type=type(error).__name__)
        if settled is None:
            return
        if settled.closed:
            await self._closer.ended(record.run_id, CloseReason.DECIDED, settled.note_id)
        if settled.resumes and record.thread_id is not None:
            resume = ResumePayload(
                home=home, user_id=record.user_id, run_id=record.run_id,
                thread_id=record.thread_id, action_id=record.id,
            )  # fmt: skip
            await self._hand_over(resume)

    async def _hand_over(self, resume: ResumePayload) -> None:
        try:
            await self._queue.send(RESUME_RUN, resume)
        except (*REDIS_FAILURES, TaskQueueUnavailableError) as error:
            log.warning("Прогон Leo не передан на эпилог", error_type=type(error).__name__)
            await self._closer.lose(resume)
