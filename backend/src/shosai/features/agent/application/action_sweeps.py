"""The minute's sweep of actions nobody is deciding or carrying out (Leo §8.4 rules 2, 3).

As the sweep role it lists, per home, the actions that need it, and settles each in its
person's transaction with the same condition a decider or an executor would use, so the sweep
never wins a race it should lose. A card past its hour expires. An approved action no worker
claimed within a minute is handed to the `agent` queue again — its claim is single-winner, so
a second hand-over is harmless — and one still unclaimed after ten minutes fails without having
started. An action `executing` whose executor fell silent past its lease ends with what is
known: an item that had started is `outcome_unknown`, one that had not failed, and nothing is
retried. Each end is audited and settles its paused run — the note, then the epilogue or the
close. A run still paused five minutes after its action ended lost its hand-over with a
worker, and closes without its epilogue.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Final
from uuid import UUID

import structlog
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.kv.connection import REDIS_FAILURES
from shosai.core.tasks.errors import TaskQueueUnavailableError
from shosai.features.agent.application.action_decisions import (
    RUN_ACTION,
    ActionPayload,
    ActionQueue,
)
from shosai.features.agent.application.action_rows import (
    ACTION,
    AuditEntry,
    audit,
    items_of,
    moved,
)
from shosai.features.agent.application.friction_judging import FrictionJudging
from shosai.features.agent.application.paused_runs import AFTER_APPROVAL, PausedRuns, Settled
from shosai.features.agent.application.run_resumption import ResumePayload
from shosai.features.agent.domain.action_items import ItemCode, ItemState, lost
from shosai.features.agent.domain.actions import (
    ActionEvent,
    ActionStatus,
    AuditEvent,
    finishing_event,
    transition,
)
from shosai.features.agent.domain.runs import RunStatus
from shosai.features.agent.infrastructure.action_metrics import ActionMetrics
from shosai.features.agent.infrastructure.run_records import AgentActionRecord, AgentRunRecord

BATCH: Final = 200
HAND_OVER_AGAIN: Final = timedelta(minutes=1)
GIVE_UP: Final = timedelta(minutes=10)
# Дольше самого долгого пункта: исполнитель обновляет действие после каждого.
EXECUTION_LEASE: Final = timedelta(minutes=5)
# Дольше очереди `agent` под нагрузкой: прогон, не взятый на эпилог за это время, закрывается.
RESUME_GRACE: Final = timedelta(minutes=5)
RUN = AgentRunRecord
# Концы, которые аудирует сам обход; исполненные пункты аудирует событие среза.
ENDS: Final = {
    ActionStatus.EXPIRED: AuditEvent.EXPIRED,
    ActionStatus.FAILED: AuditEvent.FAILED,
    ActionStatus.OUTCOME_UNKNOWN: AuditEvent.OUTCOME_UNKNOWN,
}
log = structlog.stdlib.get_logger(__name__)


class ActionSweeps:
    """Settles the home's actions that wait on nobody."""

    def __init__(
        self,
        transactions: HomeTransactions,
        parts: tuple[ActionQueue, PausedRuns, ActionMetrics],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        judging: FrictionJudging | None = None,
    ) -> None:
        self._transactions = transactions
        self._tasks, self._paused, self._metrics = parts
        self._clock = clock
        self._judging = judging

    async def sweep(self, home: Home) -> int:
        """Settle what is due in the home; how many actions moved or were handed over, and runs
        closed without their epilogue."""
        now = self._clock()
        due = (
            select(ACTION.id, ACTION.user_id, ACTION.status, ACTION.approved_at)
            .where(
                or_(
                    (ACTION.status == ActionStatus.PROPOSED.value) & (ACTION.expires_at <= now),
                    (ACTION.status == ActionStatus.APPROVED.value)
                    & (ACTION.approved_at <= now - HAND_OVER_AGAIN),
                    (ACTION.status == ActionStatus.EXECUTING.value)
                    & (ACTION.updated_at <= now - EXECUTION_LEASE),
                )
            )
            .order_by(ACTION.updated_at)
            .limit(BATCH)
        )
        async with self._transactions.begin(
            TenancyScope(home), read_only=True, sweep=True
        ) as session:
            rows = (await session.execute(due)).all()
        settled = 0
        for action_id, user_id, status, approved_at in rows:
            scope = TenancyScope(home, user_id)
            match ActionStatus(status):
                case ActionStatus.PROPOSED:
                    settled += await self._end(scope, action_id, ActionEvent.EXPIRE, now)
                case ActionStatus.APPROVED if (
                    approved_at is not None and approved_at > now - GIVE_UP
                ):
                    settled += await self._hand_over(scope, action_id)
                case ActionStatus.APPROVED:
                    settled += await self._end(scope, action_id, ActionEvent.FAIL, now)
                case _:
                    settled += await self._end_lost(scope, action_id, now)
        if settled:
            log.info("Обход действий Leo", home=home.value, actions=settled)
        return settled + await self.close_unresumed(home)

    async def _hand_over(self, scope: TenancyScope, action_id: UUID) -> int:
        payload = ActionPayload(home=scope.home, user_id=scope.user_id, action_id=action_id)
        try:
            await self._tasks.send(RUN_ACTION, payload)
        except (*REDIS_FAILURES, TaskQueueUnavailableError) as error:
            log.warning("Одобренное действие снова не передано", error_type=type(error).__name__)
            return 0
        return 1

    async def _end(
        self, scope: TenancyScope, action_id: UUID, event: ActionEvent, now: datetime
    ) -> int:
        """Expire a card past its hour, or fail an approval nobody claimed — its items never
        started."""
        async with self._transactions.begin(scope) as session:
            if event is ActionEvent.EXPIRE:
                record = await moved(
                    session, action_id, transition(ActionStatus.PROPOSED, event),
                    {"updated_at": now}, ACTION.expires_at <= now,
                )  # fmt: skip
            else:
                record = await self._failed_unclaimed(session, action_id, now)
            settled = await self._closed(session, record, now)
        return await self._told(scope, record, settled)

    async def _failed_unclaimed(
        self, session: AsyncSession, action_id: UUID, now: datetime
    ) -> AgentActionRecord | None:
        current = await session.get(ACTION, action_id)
        if current is None:
            return None
        items = [
            item.with_state(ItemState.FAILED, ItemCode.NOT_STARTED.value)
            for item in items_of(current)
        ]
        return await moved(
            session, action_id, transition(ActionStatus.APPROVED, ActionEvent.FAIL),
            {"items": [item.stored() for item in items], "updated_at": now},
            ACTION.approved_at <= now - GIVE_UP,
        )  # fmt: skip

    async def _end_lost(self, scope: TenancyScope, action_id: UUID, now: datetime) -> int:
        """End an action whose executor fell silent: what started is unknown, nothing retried."""
        async with self._transactions.begin(scope) as session:
            current = await session.get(ACTION, action_id)
            if current is None or current.status != ActionStatus.EXECUTING.value:
                return 0
            items = lost(items_of(current))
            event = finishing_event([item.outcome for item in items])
            record = await moved(
                session, action_id, transition(ActionStatus.EXECUTING, event),
                {"items": [item.stored() for item in items], "updated_at": now},
                ACTION.updated_at <= now - EXECUTION_LEASE,
            )  # fmt: skip
            settled = await self._closed(session, record, now)
        return await self._told(scope, record, settled)

    async def _closed(
        self, session: AsyncSession, record: AgentActionRecord | None, now: datetime
    ) -> Settled | None:
        """The end's audit row and its run's note, in the same transaction."""
        if record is None:
            return None
        event = ENDS.get(ActionStatus(record.status))
        if event is not None:
            code = next((item.code for item in items_of(record) if item.code), None)
            audit(session, record, AuditEntry(event, code=code), now)
        return await self._paused.settle(session, record)

    async def _told(
        self, scope: TenancyScope, record: AgentActionRecord | None, settled: Settled | None
    ) -> int:
        if record is None:
            return 0
        self._metrics.decided(record.origin, record.status)
        if self._judging is not None:
            self._judging.ended(scope.home, record.id, record.status)
        if record.approved_at is not None:
            waited = (record.updated_at - record.approved_at).total_seconds()
            self._metrics.ended_after_approval(record.status, waited)
        await self._paused.tell(scope.home, record, settled)
        return 1

    async def close_unresumed(self, home: Home) -> int:
        """Close the runs still paused well after their action ended: their epilogue never
        came — the hand-over was lost with its worker — and their note is already written."""
        now = self._clock()
        later = aliased(ACTION)
        stuck = (
            select(RUN.id, RUN.user_id, RUN.thread_id, ACTION.id)
            .join(ACTION, ACTION.run_id == RUN.id)
            .where(
                RUN.status == RunStatus.PAUSED.value,
                ACTION.status.in_(tuple(status.value for status in AFTER_APPROVAL)),
                ACTION.updated_at <= now - RESUME_GRACE,
                # Прогон, вставший на следующую карточку, ждёт её, а не эпилога прежней.
                ~select(later.id)
                .where(later.run_id == RUN.id, later.created_at > ACTION.created_at)
                .exists(),
            )
            .limit(BATCH)
        )
        async with self._transactions.begin(
            TenancyScope(home), read_only=True, sweep=True
        ) as session:
            rows = (await session.execute(stuck)).all()
        for run_id, user_id, thread_id, action_id in rows:
            resume = ResumePayload(
                home=home, user_id=user_id, run_id=run_id, thread_id=thread_id,
                action_id=action_id,
            )  # fmt: skip
            await self._paused.closer.lose(resume)
        if rows:
            log.warning("Прогоны Leo без эпилога закрыты", home=home.value, runs=len(rows))
        return len(rows)
