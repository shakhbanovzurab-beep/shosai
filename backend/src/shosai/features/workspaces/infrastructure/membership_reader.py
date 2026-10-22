"""A person's memberships, read in the caller's transaction (`MembershipReader`, §7).

Row-level security lets a person read their own memberships whatever their state, so the
reader answers for a hidden or removed membership too; nothing here is cached.
"""

from collections.abc import Collection, Mapping
from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.features.workspaces.contracts import ActiveMembership, WorkspaceFacts
from shosai.features.workspaces.domain.memberships import STANDING, MembershipState
from shosai.features.workspaces.domain.roles import WorkspaceRole
from shosai.features.workspaces.infrastructure.organization_records import (
    Membership,
    Organization,
    Project,
)

ACTIVE_WORKSPACE = "active"


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

    async def members(
        self, session: AsyncSession, org_id: UUID, user_ids: Collection[UUID]
    ) -> Mapping[UUID, ActiveMembership]:
        """The active members of an active workspace among `user_ids`, by person."""
        if not user_ids:
            return {}
        rows = await session.execute(
            select(Membership.user_id, Membership.id, Membership.role)
            .join(Organization, Organization.id == Membership.org_id)
            .where(
                Membership.org_id == org_id,
                Membership.user_id.in_(list(user_ids)),
                Membership.state == MembershipState.ACTIVE,
                Organization.state == ACTIVE_WORKSPACE,
            )
        )
        return {
            user_id: ActiveMembership(org_id, membership_id, WorkspaceRole(role))
            for user_id, membership_id, role in rows
        }


class WorkspaceDirectory:
    """Reads workspaces and their projects in the home of the transaction."""

    async def workspaces(
        self, session: AsyncSession, org_ids: Collection[UUID]
    ) -> Mapping[UUID, WorkspaceFacts]:
        """The workspaces among `org_ids` row-level security lets the person read."""
        if not org_ids:
            return {}
        rows = await session.execute(
            select(Organization.id, Organization.slug, Organization.name).where(
                Organization.id.in_(list(org_ids))
            )
        )
        return {org_id: WorkspaceFacts(org_id, slug, name) for org_id, slug, name in rows}

    async def projects(
        self, session: AsyncSession, org_id: UUID, project_ids: Collection[UUID]
    ) -> frozenset[UUID]:
        """The projects of the workspace among `project_ids`."""
        if not project_ids:
            return frozenset()
        found = await session.scalars(
            select(Project.id).where(Project.org_id == org_id, Project.id.in_(list(project_ids)))
        )
        return frozenset(found)
