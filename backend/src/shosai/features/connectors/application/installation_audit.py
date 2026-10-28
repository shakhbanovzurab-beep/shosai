"""A workspace's installations in its audit log, by its admins only (inv-17, CN-D3).

The person finishing an installation must still be an owner or an admin of the workspace
when the provider returns; the audit row names their membership and the installation, with
the workspace's existing `settings_changed` action and the code `<app>:installed` or
`<app>:removed`, so the audit's closed set needs no new action for connectors.
"""

from typing import Final
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.ports.directory import PortDirectory
from shosai.features.connectors.domain.catalogue import App
from shosai.features.workspaces.contracts import (
    AUDIT_LOG,
    MEMBERSHIP_READER,
    AuditAction,
    AuditEntry,
    WorkspaceRole,
)

ADMINS: Final = frozenset({WorkspaceRole.OWNER, WorkspaceRole.ADMIN})
TARGET_KIND: Final = "integration"


class InstallationAudit:
    """Checks the admin and writes the audit row in the caller's transaction."""

    def __init__(self, ports: PortDirectory) -> None:
        self._ports = ports

    async def admin_membership(
        self, session: AsyncSession, org_id: UUID, user_id: UUID
    ) -> UUID | None:
        """The person's membership in the workspace while they are its owner or admin."""
        memberships = await self._ports.get(MEMBERSHIP_READER).active(session, user_id)
        for membership in memberships:
            if membership.org_id == org_id and membership.role in ADMINS:
                return membership.membership_id
        return None

    async def installed(
        self, session: AsyncSession, org_id: UUID, details: tuple[UUID | None, UUID, App]
    ) -> None:
        """The audit row of an installation made."""
        await self._record(session, org_id, details, "installed")

    async def removed(
        self, session: AsyncSession, org_id: UUID, details: tuple[UUID | None, UUID, App]
    ) -> None:
        """The audit row of an installation removed."""
        await self._record(session, org_id, details, "removed")

    async def _record(
        self,
        session: AsyncSession,
        org_id: UUID,
        details: tuple[UUID | None, UUID, App],
        what: str,
    ) -> None:
        membership_id, connection_id, app = details
        entry = AuditEntry(
            org_id=org_id, action=AuditAction.SETTINGS_CHANGED, actor_membership_id=membership_id,
            target_kind=TARGET_KIND, target_id=connection_id, value=f"{app.value}:{what}",
        )  # fmt: skip
        await self._ports.get(AUDIT_LOG).record(session, entry)
