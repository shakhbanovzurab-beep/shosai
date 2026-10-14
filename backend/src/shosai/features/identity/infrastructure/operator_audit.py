"""Writing the operators' audit log in the EU home (SM-12, nfr-17).

The row's id is the event's: a delivery repeated after a failure finds the row and writes
nothing, so every action leaves exactly one row.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.features.identity.contracts import OperatorActed
from shosai.features.identity.infrastructure.operator_records import OperatorAuditEvent


async def record_action(
    session: AsyncSession, event_id: UUID, occurred_at: datetime, event: OperatorActed
) -> None:
    """One audit row of the action, in the caller's EU transaction."""
    await session.execute(
        insert(OperatorAuditEvent)
        .values(
            id=event_id, created_at=occurred_at, operator_id=event.operator_id,
            target_user_id=event.target_user_id, target_home=event.target_home.value,
            action=event.action.value, reason_code=event.reason_code,
        )
        .on_conflict_do_nothing()
    )  # fmt: skip
