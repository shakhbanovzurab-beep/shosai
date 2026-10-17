"""Members of a workspace: their role and teams, removal and leaving (§7, §3.6).

Every action runs in one transaction of the workspace's scope, reads the actor's role in
it, decides with the domain's rules and leaves one audit row. Joining is `admission`.
"""

from collections.abc import Collection
from http import HTTPStatus
from uuid import UUID

from sqlalchemy import delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.workspaces.application.acting import (
    acting_member,
    refuse_unless,
)
from shosai.features.workspaces.application.departures import Ending, end_membership
from shosai.features.workspaces.contracts import (
    AuditAction,
    AuditEntry,
    AuditLog,
)
from shosai.features.workspaces.contracts.events import (
    MemberRoleChanged,
)
from shosai.features.workspaces.domain.memberships import STANDING, MembershipState, RemovalReason
from shosai.features.workspaces.domain.roles import (
    TeamChange,
    WorkspaceAction,
    WorkspaceRole,
    may,
    may_change_teams,
    may_manage_member,
    may_set_role,
)
from shosai.features.workspaces.infrastructure.organization_records import (
    Membership,
    Team,
    TeamMember,
)


class Members:
    """Roles, teams, removals and departures of members."""

    def __init__(
        self, transactions: HomeTransactions, outbox: EventOutbox, audit: AuditLog
    ) -> None:
        self._transactions = transactions
        self._outbox = outbox
        self._audit = audit

    async def change_role(self, scope: TenancyScope, target_id: UUID, role: WorkspaceRole) -> None:
        """Give a member a new role; ownership moves only by transfer."""
        org_id, user_id = _org_and_user(scope)
        async with self._transactions.begin(scope) as session:
            acting = await acting_member(session, org_id, user_id, lock=True)
            target_role = await _member_role(session, org_id, target_id)
            refuse_unless(allowed=may_set_role(acting.actor, target_id, target_role, role))
            await session.execute(
                update(Membership).where(Membership.id == target_id).values(role=role)
            )
            entry = AuditEntry(
                org_id,
                AuditAction.ROLE_CHANGED,
                acting.actor.membership_id,
                "membership",
                target_id,
                role,
            )
            await self._audit.record(session, entry)
            await self._outbox.add(
                session, MemberRoleChanged(org_id=org_id, membership_id=target_id, role=role)
            )

    async def set_teams(
        self, scope: TenancyScope, target_id: UUID, team_ids: Collection[UUID]
    ) -> None:
        """Place a member in exactly these teams of the workspace."""
        org_id, user_id = _org_and_user(scope)
        wanted = frozenset(team_ids)
        async with self._transactions.begin(scope) as session:
            acting = await acting_member(session, org_id, user_id)
            target_role = await _member_role(session, org_id, target_id)
            rows = await session.execute(select(Team.id, Team.private).where(Team.org_id == org_id))
            teams = {team_id: private for team_id, private in rows}
            if not wanted <= teams.keys():
                raise AppError("teams_invalid", HTTPStatus.UNPROCESSABLE_ENTITY)
            current = frozenset(
                await session.scalars(
                    select(TeamMember.team_id).where(TeamMember.membership_id == target_id)
                )
            )
            added = wanted - current
            change = TeamChange(target_id, target_role, tuple(teams[team] for team in added))
            refuse_unless(allowed=may_change_teams(acting.actor, change))
            await _place(session, org_id, target_id, added, current - wanted)
            entry = AuditEntry(
                org_id,
                AuditAction.TEAM_CHANGED,
                acting.actor.membership_id,
                "membership",
                target_id,
                "teams",
            )
            await self._audit.record(session, entry)

    async def remove(self, scope: TenancyScope, target_id: UUID) -> None:
        """An admin removes a member; never the owner, never themselves."""
        org_id, user_id = _org_and_user(scope)
        async with self._transactions.begin(scope) as session:
            acting = await acting_member(session, org_id, user_id, lock=True)
            target = (
                await session.execute(
                    select(Membership.user_id, Membership.role).where(
                        Membership.id == target_id,
                        Membership.org_id == org_id,
                        Membership.state.in_([state.value for state in STANDING]),
                    )
                )
            ).first()
            if target is None:
                raise AppError("member_not_found", HTTPStatus.NOT_FOUND)
            refuse_unless(
                allowed=may_manage_member(acting.actor, target_id, WorkspaceRole(target[1]))
            )
            ending = Ending(
                org_id,
                target_id,
                target[0],
                RemovalReason.REMOVED_BY_ADMIN,
                acting.actor.membership_id,
            )
            await end_membership(session, ending, self._outbox, self._audit)

    async def leave(self, scope: TenancyScope) -> None:
        """The person leaves the workspace; the owner hands ownership over first."""
        org_id, user_id = _org_and_user(scope)
        async with self._transactions.begin(scope) as session:
            acting = await acting_member(session, org_id, user_id, lock=True)
            if not may(
                acting.actor, WorkspaceAction.LEAVE, members_can_invite=acting.members_can_invite
            ):
                raise AppError("owner_cannot_leave", HTTPStatus.CONFLICT)
            membership_id = acting.actor.membership_id
            ending = Ending(org_id, membership_id, user_id, RemovalReason.LEFT, membership_id)
            await end_membership(session, ending, self._outbox, self._audit)


def _org_and_user(scope: TenancyScope) -> tuple[UUID, UUID]:
    """The workspace and the person of a member's action; both are required."""
    if scope.org_id is None or scope.user_id is None:
        message = "действие участника идёт в скоупе пространства и человека"
        raise ValueError(message)
    return scope.org_id, scope.user_id


async def _member_role(session: AsyncSession, org_id: UUID, membership_id: UUID) -> WorkspaceRole:
    role = await session.scalar(
        select(Membership.role).where(
            Membership.id == membership_id,
            Membership.org_id == org_id,
            Membership.state == MembershipState.ACTIVE,
        )
    )
    if role is None:
        raise AppError("member_not_found", HTTPStatus.NOT_FOUND)
    return WorkspaceRole(role)


async def _place(
    session: AsyncSession,
    org_id: UUID,
    membership_id: UUID,
    added: Collection[UUID],
    removed: Collection[UUID],
) -> None:
    if removed:
        await session.execute(
            delete(TeamMember).where(
                TeamMember.membership_id == membership_id, TeamMember.team_id.in_(list(removed))
            )
        )
    if added:
        rows = [
            {"team_id": team, "membership_id": membership_id, "org_id": org_id} for team in added
        ]
        await session.execute(insert(TeamMember), rows)
