"""The person's decision on a card: approve or reject, one winner (Leo §5.3, §8.4; step 9a).

A decision is one conditional update of a `proposed` action that is the person's, carries the
nonce the card showed and has not passed its hour; anything else is 404 `action_not_found` or
409 `action_not_pending`, and an action found past its hour is expired on the spot. An
approval is audited with its channel and handed to an agent worker on the `agent` queue; the
answer waits up to 20 s for the action's end and otherwise says `executing` — the outcome
follows as `action.updated` on the run's stream. A failed hand-over is not the person's
problem: the action stays `approved`, and the minute's sweep hands it over again. A rejection
ends the card and closes its paused run in the same transaction, with no epilogue.
"""

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from typing import Final, Protocol
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.errors import AppError
from shosai.core.kv.connection import REDIS_FAILURES
from shosai.core.tasks.declaration import NO_RETRY, TaskDeclaration
from shosai.core.tasks.errors import TaskQueueUnavailableError
from shosai.core.tasks.payloads import HomeTaskPayload
from shosai.core.tasks.queues import TaskQueue
from shosai.features.agent.application.action_rows import (
    ACTION,
    AuditEntry,
    action_row,
    audit,
    moved,
)
from shosai.features.agent.application.friction_judging import FrictionJudging
from shosai.features.agent.application.paused_runs import PausedRuns
from shosai.features.agent.domain.actions import (
    TERMINAL,
    ActionEvent,
    ActionStatus,
    ApprovedVia,
    AuditEvent,
    transition,
)
from shosai.features.agent.domain.runs import APPROVAL_WAIT
from shosai.features.agent.infrastructure.action_metrics import ActionMetrics
from shosai.features.agent.infrastructure.run_records import AgentActionRecord
from shosai.features.identity.contracts import Principal

POLL_FIRST: Final = timedelta(milliseconds=100)
POLL_MOST: Final = timedelta(milliseconds=500)
log = structlog.stdlib.get_logger(__name__)


class ActionPayload(HomeTaskPayload):
    """An approved action for an agent worker to carry out."""

    action_id: UUID


RUN_ACTION: Final = TaskDeclaration(
    name="agent.run_action",
    queue=TaskQueue.AGENT,
    payload=ActionPayload,
    deadline=timedelta(minutes=3),
    retry=NO_RETRY,
)


def not_found() -> AppError:
    """No action of the person by this id."""
    return AppError("action_not_found", HTTPStatus.NOT_FOUND)


def not_pending() -> AppError:
    """The card no longer waits, or it is not the card the person saw."""
    return AppError("action_not_pending", HTTPStatus.CONFLICT)


@dataclass(frozen=True, slots=True)
class Decided:
    """The action after the decision, as the person's card now reads."""

    record: AgentActionRecord


class ActionQueue(Protocol):
    """Sends an approved action to the `agent` queue."""

    async def send(self, task: TaskDeclaration[ActionPayload], payload: ActionPayload) -> str:
        """Queue the action's execution; its task id."""
        ...


class ActionDecisions:
    """Approves and rejects the person's cards."""

    def __init__(
        self,
        transactions: HomeTransactions,
        parts: tuple[ActionQueue, PausedRuns, ActionMetrics],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        wait: timedelta = APPROVAL_WAIT,
        judging: FrictionJudging | None = None,
    ) -> None:
        self._transactions = transactions
        self._tasks, self._paused, self._metrics = parts
        self._clock = clock
        self._wait = wait
        self._judging = judging

    async def approve(self, principal: Principal, action_id: UUID, nonce: str) -> Decided:
        """Approve the card and wait a while for its outcome."""
        record = await self._decide(principal, (action_id, nonce), ActionEvent.APPROVE)
        self._metrics.approved((record.updated_at - record.created_at).total_seconds())
        if self._judging is not None:
            self._judging.ended(principal.home, record.id, record.status, approved=True)
        payload = ActionPayload(home=principal.home, user_id=principal.user_id, action_id=record.id)
        try:
            await self._tasks.send(RUN_ACTION, payload)
        except (*REDIS_FAILURES, TaskQueueUnavailableError) as error:
            log.warning("Одобренное действие не передано воркеру", error_type=type(error).__name__)
            return Decided(record)
        return Decided(await self._outcome(principal, record))

    async def reject(self, principal: Principal, action_id: UUID, nonce: str) -> Decided:
        """Reject the card; its paused run closes without an epilogue."""
        return Decided(await self._decide(principal, (action_id, nonce), ActionEvent.REJECT))

    async def _decide(
        self, principal: Principal, card: tuple[UUID, str], event: ActionEvent
    ) -> AgentActionRecord:
        action_id, nonce = card
        now = self._clock()
        async with self._transactions.begin(principal.scope()) as session:
            values: dict[str, object] = {"updated_at": now}
            if event is ActionEvent.APPROVE:
                values |= {"approved_at": now, "approved_via": ApprovedVia.WEB.value}
            record = await moved(
                session, action_id, transition(ActionStatus.PROPOSED, event), values,
                ACTION.user_id == principal.user_id, ACTION.nonce == nonce, ACTION.expires_at > now,
            )  # fmt: skip
            if record is None:
                ended = await self._expire_if_due(session, principal, action_id, now)
            else:
                ended = record if event is ActionEvent.REJECT else None
                audited = (
                    AuditEvent.APPROVED if event is ActionEvent.APPROVE else AuditEvent.REJECTED
                )
                audit(session, record, AuditEntry(audited, via=ApprovedVia.WEB.value), now)
            settled = await self._paused.settle(session, ended) if ended is not None else None
        if ended is not None:
            self._metrics.decided(ended.origin, ended.status)
            if self._judging is not None:
                self._judging.ended(principal.home, ended.id, ended.status)
            await self._paused.tell(principal.home, ended, settled)
        if record is None:
            raise (
                not_found()
                if ended is None and not await self._exists(principal, action_id)
                else not_pending()
            )
        return record

    async def _expire_if_due(
        self, session: AsyncSession, principal: Principal, action_id: UUID, now: datetime
    ) -> AgentActionRecord | None:
        """A card of the person found past its hour, expired here and now; None otherwise."""
        expired = await moved(
            session, action_id, transition(ActionStatus.PROPOSED, ActionEvent.EXPIRE),
            {"updated_at": now}, ACTION.user_id == principal.user_id, ACTION.expires_at <= now,
        )  # fmt: skip
        if expired is not None:
            audit(session, expired, AuditEntry(AuditEvent.EXPIRED), now)
        return expired

    async def _exists(self, principal: Principal, action_id: UUID) -> bool:
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            return await action_row(session, action_id, principal.user_id) is not None

    async def _outcome(self, principal: Principal, record: AgentActionRecord) -> AgentActionRecord:
        """The action once it ends, or as it stands when the wait runs out."""
        until = time.monotonic() + self._wait.total_seconds()
        pause = POLL_FIRST.total_seconds()
        current = record
        while ActionStatus(current.status) not in TERMINAL and time.monotonic() < until:
            await asyncio.sleep(min(pause, max(until - time.monotonic(), 0.0)))
            pause = min(pause * 2, POLL_MOST.total_seconds())
            async with self._transactions.begin(principal.scope(), read_only=True) as session:
                current = await action_row(session, record.id, principal.user_id) or current
        return current
