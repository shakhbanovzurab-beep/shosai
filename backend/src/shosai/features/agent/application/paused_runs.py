"""A paused run closed once its action is decided (Leo §5.3 step 4; agent step 9a).

Whatever the person decides — approve, reject, or let it expire — the action lives in the
database and ends there; its run then closes `completed` with the reason it had no epilogue,
and a server note joins the thread: the person's history shows the card's end, and Leo's next
turns read what happened in plain words. The note and the closing commit with the run's
condition, so of two deciders only one writes them. The run's log, kept while the card
waited, carries `action.updated` and then `run.completed` to a cabinet still following.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Final
from uuid import UUID

import structlog
from pydantic import JsonValue
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.ids import new_id
from shosai.core.kv.connection import REDIS_FAILURES
from shosai.features.agent.application.action_cards import action_card
from shosai.features.agent.application.action_rows import items_of
from shosai.features.agent.application.turn_task import RunEmitter
from shosai.features.agent.contracts.events import TurnCompleted
from shosai.features.agent.domain.endings import closed
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

RUN = AgentRunRecord
NO_CODE: Final = "unknown"
log = structlog.stdlib.get_logger(__name__)


def action_note(record: AgentActionRecord) -> str:
    """What Leo's later turns read of the decided action: English, registered."""
    items = items_of(record)
    code = next((item.code for item in items if item.code), None) or NO_CODE
    outcome = ACTION_OUTCOMES[record.status].format(code=code)
    return ACTION_NOTE.format(tool=items[0].tool, outcome=outcome)


class PausedRuns:
    """Closes the run a decided action paused, and tells its cabinet."""

    def __init__(
        self,
        writers: tuple[HomeTransactions, EventOutbox],
        run_log: RunLog,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions, self._outbox = writers
        self._log = run_log
        self._clock = clock

    async def close(
        self, session: AsyncSession, record: AgentActionRecord, reason: CloseReason
    ) -> UUID | None:
        """In the decider's transaction: close the run and add the note; the note's id, or None
        when the run was not paused any more."""
        if record.run_id is None or record.thread_id is None:
            return None
        now = self._clock()
        won = await session.scalar(
            update(RUN)
            .where(RUN.id == record.run_id, RUN.status == RunStatus.PAUSED.value)
            .values(status=RunStatus.COMPLETED.value, outcome_code=reason.value, ended_at=now)
            .returning(RUN.id)
        )
        thread = await session.scalar(
            select(AgentThreadRecord).where(AgentThreadRecord.id == record.thread_id)
        )
        if won is None or thread is None:
            return None
        note_id = new_id()
        session.add(
            AgentMessageRecord(
                id=note_id, created_at=now, thread_id=thread.id, user_id=thread.user_id,
                run_id=record.run_id, role=MessageRole.SERVER.value, text="",
                action_ids=[record.id], digest={"text": action_note(record)},
            )
        )  # fmt: skip
        thread.last_activity_at = now
        completed = TurnCompleted(thread_id=thread.id, run_id=record.run_id, user_id=thread.user_id)
        await self._outbox.add(session, completed)
        return note_id

    async def tell(
        self,
        record: AgentActionRecord,
        note_id: UUID | None,
        invalidates: tuple[str, ...] = (),
    ) -> None:
        """After the commit: the card's new state on the run's log, and the run's end when this
        decision closed it. A log gone with its hour is left gone: the cabinet reloads."""
        if record.run_id is None:
            return
        try:
            last = await self._log.last(record.run_id)
            if last is None:
                return
            emitter = RunEmitter(self._log, record.run_id, after=last.seq)
            updated: dict[str, JsonValue] = {"action": action_card(record)}
            if invalidates:
                updated["invalidates"] = list(invalidates)
            await emitter.emit(EventKind.ACTION_UPDATED, updated)
            if note_id is not None:
                await emitter.emit(*closed(CloseReason.CHECKPOINT_LOST).terminal(note_id))
        except REDIS_FAILURES as error:
            # Решение записано в базе: кабинет возьмёт его из истории и карточки.
            log.warning("Решение по карточке не попало в журнал", error_type=type(error).__name__)
