"""An action's row and its audit, each transition one conditional update (Leo §8.4 rule 1).

Every change of status names the status it expects in its `WHERE`, so two tabs, a double click
or the sweep racing a decision have exactly one winner; the loser gets nothing back. Items move
only while the action is `executing`, so an executor the sweep gave up on can write nothing
more. Each transition the gateway makes is audited in the same transaction, with codes only;
an item's effect is audited by its slice's own event (`agent.action_item.executed`).
"""

from collections.abc import Collection, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final
from uuid import UUID

from sqlalchemy import ColumnElement, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.kernel.ids import new_id
from shosai.features.agent.domain.action_items import ActionItem, item_of
from shosai.features.agent.domain.actions import TERMINAL, ActionStatus, AuditEvent, Transition
from shosai.features.agent.domain.endings import cancelled
from shosai.features.agent.domain.runs import RunStatus
from shosai.features.agent.infrastructure.run_records import (
    AgentActionRecord,
    AgentAuditRecord,
    AgentRunRecord,
)

ACTION = AgentActionRecord
OVER: Final = frozenset(status.value for status in TERMINAL)


def items_of(record: AgentActionRecord) -> tuple[ActionItem, ...]:
    """The row's items."""
    return tuple(item_of(raw) for raw in record.items)


@dataclass(frozen=True, slots=True)
class AuditEntry:
    """What one audit row says: the event, how it came, the item and its code."""

    event: AuditEvent
    via: str | None = None
    code: str | None = None
    item_key: str | None = None
    tool: str | None = None
    targets: int | None = None


def audit(
    session: AsyncSession, record: AgentActionRecord, entry: AuditEntry, now: datetime
) -> None:
    """One audit row of the action, in the caller's transaction; never content."""
    session.add(
        AgentAuditRecord(
            id=new_id(), created_at=now, user_id=record.user_id, action_id=record.id,
            event=entry.event.value, via=entry.via, code=entry.code, item_key=entry.item_key,
            tool_name=entry.tool, targets=entry.targets,
        )
    )  # fmt: skip


async def moved(
    session: AsyncSession,
    action_id: UUID,
    transition: Transition,
    values: dict[str, Any],
    *conditions: ColumnElement[bool],
) -> AgentActionRecord | None:
    """Apply one transition if the action is still where it expects; the row, or None."""
    fields: dict[str, Any] = {"status": transition.to.value, **values}
    now = fields.get("updated_at")
    if transition.to.value in OVER and now is not None:
        fields["resolved_at"] = now
    statement = (
        update(ACTION)
        .where(ACTION.id == action_id, ACTION.status == transition.expected.value, *conditions)
        .values(**fields)
        .returning(ACTION)
    )
    return (await session.execute(statement)).scalar_one_or_none()


async def store_items(
    session: AsyncSession, action_id: UUID, items: Sequence[ActionItem], now: datetime
) -> bool:
    """Write the items of an action still executing; False once it is not."""
    won = await session.scalar(
        update(ACTION)
        .where(ACTION.id == action_id, ACTION.status == ActionStatus.EXECUTING.value)
        .values(items=[item.stored() for item in items], updated_at=now)
        .returning(ACTION.id)
    )
    return won is not None


async def action_row(
    session: AsyncSession, action_id: UUID, user_id: UUID | None = None
) -> AgentActionRecord | None:
    """The action, as its person reads it when `user_id` names them."""
    statement = select(ACTION).where(ACTION.id == action_id)
    if user_id is not None:
        statement = statement.where(ACTION.user_id == user_id)
    return await session.scalar(statement)


async def supersede_cards(
    session: AsyncSession, user_id: UUID, thread_ids: Collection[UUID]
) -> None:
    """The deleted threads' cards can no longer be approved, and their paused runs end."""
    action = AgentActionRecord
    superseded = await session.scalars(
        update(action)
        .where(
            action.user_id == user_id,
            action.thread_id.in_(thread_ids),
            action.status == ActionStatus.PROPOSED.value,
        )
        .values(status=ActionStatus.SUPERSEDED.value, resolved_at=func.now(), updated_at=func.now())
        .returning(action)
    )
    for record in superseded:
        audit(session, record, AuditEntry(AuditEvent.SUPERSEDED), record.updated_at)
    run = AgentRunRecord
    ending = cancelled()
    await session.execute(
        update(run)
        .where(
            run.user_id == user_id,
            run.thread_id.in_(thread_ids),
            run.status == RunStatus.PAUSED.value,
        )
        .values(status=ending.status.value, outcome_code=ending.code, ended_at=func.now())
    )
