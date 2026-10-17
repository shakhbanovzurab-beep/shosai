"""The workspace audit log: one row per administrative action, in its transaction (inv-17)."""

from datetime import UTC, datetime

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.kernel.ids import new_id
from shosai.features.workspaces.contracts import AuditEntry
from shosai.features.workspaces.infrastructure.audit_records import OrgAuditEvent


class WorkspaceAuditLog:
    """Appends audit rows; the application role can never change or delete them."""

    async def record(self, session: AsyncSession, entry: AuditEntry) -> None:
        """Append one row in the caller's transaction."""
        await session.execute(
            insert(OrgAuditEvent).values(
                id=new_id(),
                created_at=datetime.now(UTC),
                org_id=entry.org_id,
                action=entry.action.value,
                actor_membership_id=entry.actor_membership_id,
                target_kind=entry.target_kind,
                target_id=entry.target_id,
                value=entry.value,
            )
        )
