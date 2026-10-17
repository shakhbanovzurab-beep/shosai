"""A person's memberships, read in the caller's transaction (`MembershipReader`, §7).

Row-level security lets a person read their own memberships whatever their state, so the
reader answers for a hidden or removed membership too; nothing here is cached.
"""

from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.features.workspaces.contracts import ActiveMembership
from shosai.features.workspaces.domain.memberships import STANDING, MembershipState
from shosai.features.workspaces.domain.roles import WorkspaceRole
from shosai.features.workspaces.infrastructure.organization_records import Membership


class MembershipDirectory:
    """Reads a person's memberships in the home of the transaction."""

    async def active(self, session: AsyncSession, user_id: UUID) -> tuple[ActiveMembership, ...]:
        """The person's active memberships."""
        rows = await session.execute(
            select(Membership.org_id, Membership.id, Membership.role)
            .where(Membership.user_id == user_id, Membership.state == MembershipState.ACTIVE)
            .order_by(Membership.joined_at)
        )
        return tuple(
            ActiveMembership(org_id, membership_id, WorkspaceRole(role))
            for org_id, membership_id, role in rows
        )

    async def has_memberships(self, session: AsyncSession, user_id: UUID) -> bool:
        """Whether the person holds an active or hidden membership."""
        standing = [state.value for state in STANDING]
        query = exists().where(Membership.user_id == user_id, Membership.state.in_(standing))
        return bool(await session.scalar(select(query)))
