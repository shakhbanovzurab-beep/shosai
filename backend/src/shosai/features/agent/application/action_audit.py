"""An item's effect into the action's audit trail (Leo §8.4 rule 6; agent step 9a).

The slice that applied an approved item wrote `agent.action_item.executed` in the effect's own
transaction; the agent turns each delivery into one `executed` row of `agent_audit` in the
person's scope, keyed by the event's id and time, so a repeated delivery adds nothing. The row
holds ids, the tool and the count of targets — never the arguments or the result.
"""

from uuid import UUID

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.agent_tools.events import ActionItemExecuted
from shosai.core.events.subscriptions import ReceivedEvent
from shosai.features.agent.domain.actions import AuditEvent
from shosai.features.agent.infrastructure.run_records import AgentAuditRecord


def action_of(item_key: str) -> UUID:
    """The action an item key belongs to: `action:index`."""
    action, _, _ = item_key.partition(":")
    return UUID(action)


async def audit_item(session: AsyncSession, received: ReceivedEvent[ActionItemExecuted]) -> None:
    """One `executed` row for the delivered event, once."""
    event, user_id = received.event, received.scope.user_id
    if user_id is None:
        message = "пункт действия Leo исполнен без человека в области события"
        raise ValueError(message)
    await session.execute(
        insert(AgentAuditRecord)
        .values(
            id=received.event_id, created_at=received.occurred_at, user_id=user_id,
            action_id=action_of(event.item_key), item_key=event.item_key, tool_name=event.tool,
            event=AuditEvent.EXECUTED.value, targets=event.targets,
        )
        .on_conflict_do_nothing(index_elements=["id", "created_at"])
    )  # fmt: skip
