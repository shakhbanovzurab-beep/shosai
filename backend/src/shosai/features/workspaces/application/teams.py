"""Teams and projects of a workspace (§7, SM-2; the cabinet's teams and projects routes).

Admins make, change and delete teams. A team with knowledge shared to it is not deleted:
its items, and the workspace's files they became, would lose their audience (409).
Deleting a team removes the grants naming it, so its meetings narrow to their
participants. Any member but a guest starts a project and leads it unless they name
someone else; its lead and admins change or delete it, and its meetings, tasks and files
stay (`project.deleted`).
"""

from collections.abc import Collection
from dataclasses import dataclass
from datetime import date
from http import HTTPStatus
from uuid import UUID

from sqlalchemy import delete, exists, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.ids import new_id
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.workspaces.application.acting import Acting, acting_member, refuse_unless
from shosai.features.workspaces.contracts import AuditAction, AuditEntry, AuditLog
from shosai.features.workspaces.contracts.events import ProjectDeleted, TeamDeleted
from shosai.features.workspaces.domain.access import GranteeKind
from shosai.features.workspaces.domain.memberships import MembershipState
from shosai.features.workspaces.domain.roles import (
    WorkspaceAction,
    WorkspaceRole,
    may,
    may_edit_project,
)
from shosai.features.workspaces.infrastructure.access_records import ResourceGrant
from shosai.features.workspaces.infrastructure.organization_records import (
    Membership,
    Project,
    Team,
    TeamMember,
)
from shosai.features.workspaces.infrastructure.share_records import FILE_KIND, KNOWLEDGE_ITEM_KIND


@dataclass(frozen=True, slots=True)
class TeamDraft:
    """A team as an admin writes it; `member_ids` are memberships of the workspace."""

    name: str
    description: str
    color: str
    private: bool
    member_ids: frozenset[UUID]


@dataclass(frozen=True, slots=True)
class ProjectDraft:
    """A project as a member writes it; None leaves the lead or the team unset."""

    name: str
    description: str
    status: str
    lead_id: UUID | None
    team_id: UUID | None
    target_date: date | None


class Teams:
    """Teams and projects, each change with its audit row."""

    def __init__(
        self, transactions: HomeTransactions, outbox: EventOutbox, audit: AuditLog
    ) -> None:
        self._transactions = transactions
        self._outbox = outbox
        self._audit = audit

    async def create_team(self, scope: TenancyScope, draft: TeamDraft) -> UUID:
        """A new team with its members."""
        team_id = new_id()
        async with self._transactions.begin(scope) as session:
            acting = await self._team_manager(session, scope)
            await _require_members(session, acting_org(scope), draft.member_ids)
            await session.execute(
                insert(Team).values(id=team_id, org_id=acting_org(scope), **_team_values(draft))
            )
            await _set_team_members(session, acting_org(scope), team_id, draft.member_ids)
            await self._record(session, scope, acting, AuditAction.TEAM_CREATED, ("team", team_id))
        return team_id

    async def update_team(self, scope: TenancyScope, team_id: UUID, draft: TeamDraft) -> None:
        """Change a team and its members."""
        async with self._transactions.begin(scope) as session:
            acting = await self._team_manager(session, scope)
            await _require_members(session, acting_org(scope), draft.member_ids)
            changed = await session.scalar(
                update(Team)
                .where(Team.id == team_id, Team.org_id == acting_org(scope))
                .values(**_team_values(draft))
                .returning(Team.id)
            )
            if changed is None:
                raise AppError("team_not_found", HTTPStatus.NOT_FOUND)
            await _set_team_members(session, acting_org(scope), team_id, draft.member_ids)
            await self._record(session, scope, acting, AuditAction.TEAM_CHANGED, ("team", team_id))

    async def delete_team(self, scope: TenancyScope, team_id: UUID) -> None:
        """Delete a team unless knowledge is shared with it."""
        org_id = acting_org(scope)
        async with self._transactions.begin(scope) as session:
            acting = await self._team_manager(session, scope)
            names_team = (
                ResourceGrant.org_id == org_id,
                ResourceGrant.grantee_kind == GranteeKind.TEAM,
                ResourceGrant.grantee_id == team_id,
            )
            shares_knowledge = exists().where(
                *names_team,
                # Файл пространства — его знание: файлового менеджера у пространства нет.
                ResourceGrant.resource_kind.in_((KNOWLEDGE_ITEM_KIND, FILE_KIND)),
            )
            if await session.scalar(select(shares_knowledge)):
                raise AppError("team_has_knowledge", HTTPStatus.CONFLICT)
            await session.execute(delete(ResourceGrant).where(*names_team))
            deleted = await session.scalar(
                delete(Team).where(Team.id == team_id, Team.org_id == org_id).returning(Team.id)
            )
            if deleted is None:
                raise AppError("team_not_found", HTTPStatus.NOT_FOUND)
            await self._record(session, scope, acting, AuditAction.TEAM_DELETED, ("team", team_id))
            await self._outbox.add(session, TeamDeleted(org_id=org_id, team_id=team_id))

    async def create_project(self, scope: TenancyScope, draft: ProjectDraft) -> UUID:
        """A new project; whoever starts it leads it unless they name another member."""
        project_id, org_id = new_id(), acting_org(scope)
        async with self._transactions.begin(scope) as session:
            acting = await acting_member(session, org_id, _user(scope))
            refuse_unless(allowed=acting.actor.role is not WorkspaceRole.GUEST)
            lead = draft.lead_id or acting.actor.membership_id
            await _require_project_refs(session, org_id, lead, draft.team_id)
            values = _project_values(draft) | {"lead_membership_id": lead}
            await session.execute(insert(Project).values(id=project_id, org_id=org_id, **values))
            await self._record(
                session, scope, acting, AuditAction.PROJECT_CREATED, ("project", project_id)
            )
        return project_id

    async def update_project(
        self, scope: TenancyScope, project_id: UUID, draft: ProjectDraft
    ) -> None:
        """Change a project; its lead or an admin."""
        org_id = acting_org(scope)
        async with self._transactions.begin(scope) as session:
            acting = await self._project_editor(session, scope, project_id)
            await _require_project_refs(session, org_id, draft.lead_id, draft.team_id)
            values = _project_values(draft) | {
                "lead_membership_id": draft.lead_id,
                "updated_at": func.now(),
            }
            await session.execute(update(Project).where(Project.id == project_id).values(**values))
            await self._record(
                session, scope, acting, AuditAction.PROJECT_CHANGED, ("project", project_id)
            )

    async def delete_project(self, scope: TenancyScope, project_id: UUID) -> None:
        """Delete a project; its meetings, tasks and files stay."""
        org_id = acting_org(scope)
        async with self._transactions.begin(scope) as session:
            acting = await self._project_editor(session, scope, project_id)
            await session.execute(delete(Project).where(Project.id == project_id))
            await self._record(
                session, scope, acting, AuditAction.PROJECT_DELETED, ("project", project_id)
            )
            await self._outbox.add(session, ProjectDeleted(org_id=org_id, project_id=project_id))

    async def _team_manager(self, session: AsyncSession, scope: TenancyScope) -> Acting:
        acting = await acting_member(session, acting_org(scope), _user(scope))
        allowed = may(
            acting.actor, WorkspaceAction.MANAGE_TEAMS, members_can_invite=acting.members_can_invite
        )
        refuse_unless(allowed=allowed)
        return acting

    async def _project_editor(
        self, session: AsyncSession, scope: TenancyScope, project_id: UUID
    ) -> Acting:
        org_id = acting_org(scope)
        acting = await acting_member(session, org_id, _user(scope))
        found = (
            await session.execute(
                select(Project.lead_membership_id).where(
                    Project.id == project_id, Project.org_id == org_id
                )
            )
        ).first()
        if found is None:
            raise AppError("project_not_found", HTTPStatus.NOT_FOUND)
        refuse_unless(allowed=may_edit_project(acting.actor, found[0]))
        return acting

    async def _record(
        self,
        session: AsyncSession,
        scope: TenancyScope,
        acting: Acting,
        action: AuditAction,
        target: tuple[str, UUID],
    ) -> None:
        kind, target_id = target
        entry = AuditEntry(acting_org(scope), action, acting.actor.membership_id, kind, target_id)
        await self._audit.record(session, entry)


def acting_org(scope: TenancyScope) -> UUID:
    """The workspace of the scope; a team or project action always names it."""
    if scope.org_id is None:
        message = "команды и проекты меняются в скоупе пространства"
        raise ValueError(message)
    return scope.org_id


def _user(scope: TenancyScope) -> UUID:
    if scope.user_id is None:
        message = "команды и проекты меняет человек"
        raise ValueError(message)
    return scope.user_id


def _team_values(draft: TeamDraft) -> dict[str, object]:
    return {
        "name": draft.name,
        "description": draft.description,
        "color": draft.color,
        "private": draft.private,
    }


def _project_values(draft: ProjectDraft) -> dict[str, object]:
    return {
        "name": draft.name,
        "description": draft.description,
        "status": draft.status,
        "team_id": draft.team_id,
        "target_date": draft.target_date,
    }


async def _require_members(
    session: AsyncSession, org_id: UUID, member_ids: Collection[UUID]
) -> None:
    if not member_ids:
        return
    found = await session.scalar(
        select(func.count()).where(
            Membership.id.in_(list(member_ids)),
            Membership.org_id == org_id,
            Membership.state == MembershipState.ACTIVE,
        )
    )
    if found != len(member_ids):
        raise AppError("members_invalid", HTTPStatus.UNPROCESSABLE_ENTITY)


async def _require_project_refs(
    session: AsyncSession, org_id: UUID, lead_id: UUID | None, team_id: UUID | None
) -> None:
    if lead_id is not None:
        await _require_members(session, org_id, {lead_id})
    if team_id is not None:
        found = await session.scalar(
            select(Team.id).where(Team.id == team_id, Team.org_id == org_id)
        )
        if found is None:
            raise AppError("team_not_found", HTTPStatus.UNPROCESSABLE_ENTITY)


async def _set_team_members(
    session: AsyncSession, org_id: UUID, team_id: UUID, member_ids: Collection[UUID]
) -> None:
    await session.execute(delete(TeamMember).where(TeamMember.team_id == team_id))
    if member_ids:
        rows = [
            {"team_id": team_id, "membership_id": member, "org_id": org_id} for member in member_ids
        ]
        await session.execute(insert(TeamMember), rows)
