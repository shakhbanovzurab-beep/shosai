"""What other slices may use of workspaces (workspaces plan §3.2, ADR 0039, ADR 0053).

Every slice that lets people share its rows reads them through `AccessPolicy`: the policy
builds the predicate a slice puts into its own query, so the access check runs in the
query that reads the resource and is never cached (§7). Slices reach workspaces' services
through the port keys below and `CoreServices.ports`; they never import its internals.
Workspaces binds each port in the step that builds it; `SeatAllowance` is billing's to
bind, and until it is bound every join is refused (ADR 0053 point 7). The events
workspaces publishes are in `contracts.events`.
"""

from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime
from typing import Final, Protocol
from uuid import UUID

from sqlalchemy import ColumnElement
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.access.shareable import ShareableResource
from shosai.core.events.domain_event import EventCode
from shosai.core.ports.keys import PortKey
from shosai.features.workspaces.domain.access import (
    AccessLevel,
    Audience,
    AudienceKind,
    Grantee,
    GranteeKind,
)
from shosai.features.workspaces.domain.audit import AuditAction
from shosai.features.workspaces.domain.memberships import MembershipState, RemovalReason
from shosai.features.workspaces.domain.roles import WorkspaceRole

__all__ = [
    "ACCESS_POLICY",
    "AUDIT_LOG",
    "MEMBERSHIP_READER",
    "SEAT_ALLOWANCE",
    "AccessChange",
    "AccessLevel",
    "AccessPolicy",
    "ActiveMembership",
    "Audience",
    "AudienceKind",
    "AuditAction",
    "AuditEntry",
    "AuditLog",
    "Grantee",
    "GranteeKind",
    "MembershipReader",
    "MembershipState",
    "PaidSeats",
    "RemovalReason",
    "SeatAllowance",
    "Viewer",
    "WorkspaceRole",
]


@dataclass(frozen=True, slots=True)
class Viewer:
    """The person reading, and the workspace a screen narrows its list to.

    `within` narrows a workspace screen to that workspace; it is not a boundary. Leo never
    sets it: the access policy alone bounds what a person reads (ADR 0053 point 8).
    """

    user_id: UUID
    within: UUID | None = None


@dataclass(frozen=True, slots=True)
class AccessChange:
    """A new access level and grants for one row of a workspace, by an acting member."""

    resource: ShareableResource
    resource_id: UUID
    org_id: UUID
    level: AccessLevel
    grantees: frozenset[Grantee]
    # None — администратор платформы.
    actor_membership_id: UUID | None


class AccessPolicy(Protocol):
    """The one access policy every read and write of a shareable resource goes through (§7)."""

    def readable(self, resource: ShareableResource, viewer: Viewer) -> ColumnElement[bool]:
        """The predicate that admits exactly the rows the viewer may read."""
        ...

    def manageable(self, resource: ShareableResource, viewer: Viewer) -> ColumnElement[bool]:
        """The predicate that admits exactly the rows whose access the viewer may change."""
        ...

    async def filter_readable(
        self,
        session: AsyncSession,
        resource: ShareableResource,
        ids: Collection[UUID],
        viewer: Viewer,
    ) -> frozenset[UUID]:
        """The ids the viewer may read now, in one query: search hits re-checked (§7)."""
        ...

    async def set_access(self, session: AsyncSession, change: AccessChange) -> None:
        """Write the level, the grants, the audit row and the event in the caller's transaction."""
        ...


@dataclass(frozen=True, slots=True)
class ActiveMembership:
    """One workspace a person belongs to, with their role there."""

    org_id: UUID
    membership_id: UUID
    role: WorkspaceRole


class MembershipReader(Protocol):
    """A person's memberships, read in the caller's transaction and never cached (§7)."""

    async def active(self, session: AsyncSession, user_id: UUID) -> tuple[ActiveMembership, ...]:
        """The person's active memberships in the home of the transaction."""
        ...

    async def has_memberships(self, session: AsyncSession, user_id: UUID) -> bool:
        """Whether the person holds an active or hidden membership (the transfer guard)."""
        ...


@dataclass(frozen=True, slots=True)
class AuditEntry:
    """One administrative action or access change; codes and ids only, no names or text."""

    org_id: UUID
    action: AuditAction
    # None — администратор платформы.
    actor_membership_id: UUID | None
    target_kind: EventCode
    target_id: UUID | None = None
    # Коды и числа: роль, ключи настроек, «10 → 12»; имена и адреса читаются при показе.
    value: EventCode | None = None


class AuditLog(Protocol):
    """Appends to the workspace audit log in the caller's transaction (inv-17)."""

    async def record(self, session: AsyncSession, entry: AuditEntry) -> None:
        """Append one row; the application role can never change or delete it."""
        ...


@dataclass(frozen=True, slots=True)
class PaidSeats:
    """The seats billing sells a workspace, and the end of its trial."""

    paid: int
    trial_ends_at: datetime | None


class SeatAllowance(Protocol):
    """Billing's seats of a workspace (fr-15); bound by billing, required for every join."""

    async def seats(self, session: AsyncSession, org_id: UUID) -> PaidSeats:
        """The seats paid for now, read under the workspace's row lock by the caller."""
        ...

    async def start_trial(self, session: AsyncSession, org_id: UUID, seats: int) -> PaidSeats:
        """Start the trial of a new workspace with this many seats."""
        ...


ACCESS_POLICY: Final = PortKey[AccessPolicy]("workspaces.access_policy")
MEMBERSHIP_READER: Final = PortKey[MembershipReader]("workspaces.membership_reader")
AUDIT_LOG: Final = PortKey[AuditLog]("workspaces.audit_log")
SEAT_ALLOWANCE: Final = PortKey[SeatAllowance]("workspaces.seat_allowance")
