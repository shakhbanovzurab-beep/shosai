"""Joining a workspace: one person becomes an active member (§7, inv-15, inv-16).

A join locks the workspace's row and counts seats there — standing members and pending
invitations — against billing's paid seats; until billing binds its port nobody joins
(ADR 0053 point 7). At launch a person joins only a workspace of their own home. A repeat
returns the same membership; a removed member comes back on a new join.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from http import HTTPStatus
from uuid import UUID

from sqlalchemy import func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.homes import Home
from shosai.core.kernel.ids import new_id
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.workspaces.application.acting import workspace_state
from shosai.features.workspaces.contracts import (
    SEAT_ALLOWANCE,
    AuditAction,
    AuditEntry,
    AuditLog,
    SeatAllowance,
)
from shosai.features.workspaces.contracts.events import JoinChannel, MemberJoined
from shosai.features.workspaces.domain.memberships import STANDING, MembershipState
from shosai.features.workspaces.domain.roles import WorkspaceRole
from shosai.features.workspaces.domain.seats import SeatUse
from shosai.features.workspaces.infrastructure.access_records import Invitation
from shosai.features.workspaces.infrastructure.organization_records import Membership


@dataclass(frozen=True, slots=True)
class Joining:
    """A person joining a workspace: who, from which home, as what and by which way."""

    org_id: UUID
    user_id: UUID
    user_home: Home
    role: WorkspaceRole
    via: JoinChannel


class Admission:
    """Admits people into workspaces."""

    def __init__(
        self,
        transactions: HomeTransactions,
        outbox: EventOutbox,
        audit: AuditLog,
        ports: PortDirectory,
    ) -> None:
        self._transactions = transactions
        self._outbox = outbox
        self._audit = audit
        self._ports = ports

    async def admit(self, home: Home, joining: Joining) -> UUID:
        """Make the person an active member; a repeat returns the same membership."""
        if joining.user_home is not home:
            raise AppError("workspace_home_mismatch", HTTPStatus.CONFLICT)
        seats = self._seats()
        scope = TenancyScope(home, joining.user_id, joining.org_id)
        async with self._transactions.begin(scope) as session:
            await workspace_state(session, joining.org_id, lock=True)
            found = (
                await session.execute(
                    select(Membership.id, Membership.state).where(
                        Membership.org_id == joining.org_id, Membership.user_id == joining.user_id
                    )
                )
            ).first()
            if found is not None and found[1] == MembershipState.ACTIVE:
                return found[0]
            if found is not None and found[1] == MembershipState.HIDDEN:
                raise AppError("membership_conflict", HTTPStatus.CONFLICT)
            use = await _seat_use(session, joining.org_id, seats)
            # Приглашение уже держит место; вступление по домену занимает новое.
            if not use.admits(0 if joining.via is JoinChannel.INVITATION else 1):
                raise AppError("seats_exhausted", HTTPStatus.PAYMENT_REQUIRED)
            membership_id = await _activate(session, joining, found[0] if found else None)
            entry = AuditEntry(
                joining.org_id,
                AuditAction.MEMBER_JOINED,
                membership_id,
                "membership",
                membership_id,
                joining.via,
            )
            await self._audit.record(session, entry)
            event = MemberJoined(
                org_id=joining.org_id,
                user_id=joining.user_id,
                membership_id=membership_id,
                via=joining.via,
            )
            await self._outbox.add(session, event)
            return membership_id

    def _seats(self) -> SeatAllowance:
        bound = self._ports.all(SEAT_ALLOWANCE)
        if not bound:
            raise AppError("seats_unavailable", HTTPStatus.SERVICE_UNAVAILABLE)
        return bound[0]


async def _seat_use(session: AsyncSession, org_id: UUID, seats: SeatAllowance) -> SeatUse:
    paid = await seats.seats(session, org_id)
    members = await session.scalar(
        select(func.count()).where(
            Membership.org_id == org_id,
            Membership.state.in_([state.value for state in STANDING]),
        )
    )
    pending = await session.scalar(
        select(func.count()).where(
            Invitation.org_id == org_id,
            Invitation.accepted_at.is_(None),
            Invitation.expires_at > datetime.now(UTC),
        )
    )
    return SeatUse(paid.paid, members or 0, pending or 0)


async def _activate(session: AsyncSession, joining: Joining, existing: UUID | None) -> UUID:
    """Insert the membership, or bring a removed one back."""
    if existing is not None:
        await session.execute(
            update(Membership)
            .where(Membership.id == existing)
            .values(
                state=MembershipState.ACTIVE,
                role=joining.role,
                removed_at=None,
                removal_reason=None,
                joined_at=datetime.now(UTC),
            )
        )
        return existing
    membership_id = new_id()
    await session.execute(
        insert(Membership).values(
            id=membership_id, org_id=joining.org_id, user_id=joining.user_id, role=joining.role
        )
    )
    return membership_id
