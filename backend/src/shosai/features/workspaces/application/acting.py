"""Who acts in a workspace, read in the action's own transaction (ADR 0039 point 6).

The token carries no workspace role: each action reads the actor's membership and the
workspace's state with its first statement. A missing workspace and a non-member answer
the same 404; a suspended workspace answers 423 (§7, the cabinet's gate).
"""

from dataclasses import dataclass
from http import HTTPStatus
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.kernel.errors import AppError
from shosai.features.workspaces.domain.memberships import MembershipState
from shosai.features.workspaces.domain.roles import Actor, WorkspaceRole
from shosai.features.workspaces.infrastructure.organization_records import (
    Membership,
    Organization,
)

ACTIVE = "active"
SUSPENDED = "suspended"


@dataclass(frozen=True, slots=True)
class Acting:
    """The acting member and the workspace setting their rights depend on."""

    actor: Actor
    members_can_invite: bool


def refuse_unless(*, allowed: bool) -> None:
    """403 when the domain's rules do not let the actor do it."""
    if not allowed:
        raise AppError("not_allowed", HTTPStatus.FORBIDDEN)


async def workspace_state(session: AsyncSession, org_id: UUID, *, lock: bool) -> str:
    """The workspace's state, its row locked for seats and ownership when `lock` is set."""
    query = select(Organization.state).where(Organization.id == org_id)
    state = await session.scalar(query.with_for_update() if lock else query)
    if state is None or state not in {ACTIVE, SUSPENDED}:
        raise AppError("workspace_not_found", HTTPStatus.NOT_FOUND)
    if state == SUSPENDED:
        raise AppError("workspace_suspended", HTTPStatus.LOCKED)
    return state


async def acting_member(
    session: AsyncSession, org_id: UUID, user_id: UUID, *, lock: bool = False
) -> Acting:
    """The person's active membership in an active workspace, or 404 or 423."""
    await workspace_state(session, org_id, lock=lock)
    row = (
        await session.execute(
            select(Membership.id, Membership.role, Organization.members_can_invite)
            .join(Organization, Organization.id == Membership.org_id)
            .where(
                Membership.org_id == org_id,
                Membership.user_id == user_id,
                Membership.state == MembershipState.ACTIVE,
            )
        )
    ).first()
    if row is None:
        raise AppError("workspace_not_found", HTTPStatus.NOT_FOUND)
    membership_id, role, members_can_invite = row
    return Acting(Actor(membership_id, WorkspaceRole(role)), members_can_invite)
