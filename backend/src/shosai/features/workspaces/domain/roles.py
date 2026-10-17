"""Roles inside a workspace and what each may do (§7; the cabinet's `domain/roles.ts`).

The token carries no workspace role (ADR 0039): a role is read from the membership in
the same transaction as the action, and these rules decide on it. Admin rights manage
the workspace; they never widen what a member may read (the access policy decides that).
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Final
from uuid import UUID


class WorkspaceRole(StrEnum):
    """A member's role; guest stays in the model without a screen (§7)."""

    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    # Видит только явно выданное; экрана пока нет.
    GUEST = "guest"


# Владельца не назначают: им становятся при создании или передаче владения.
ASSIGNABLE_ROLES: Final = frozenset({WorkspaceRole.ADMIN, WorkspaceRole.MEMBER})
MANAGING_ROLES: Final = frozenset({WorkspaceRole.OWNER, WorkspaceRole.ADMIN})


class WorkspaceAction(StrEnum):
    """An action on the workspace as a whole."""

    INVITE = "invite"
    MANAGE_PEOPLE = "manage_people"
    MANAGE_TEAMS = "manage_teams"
    EDIT_SETTINGS = "edit_settings"
    CONNECT_SOURCES = "connect_sources"
    READ_USAGE = "read_usage"
    MANAGE_BILLING = "manage_billing"
    DELETE_WORKSPACE = "delete_workspace"
    EXPORT_WORKSPACE = "export_workspace"
    LEAVE = "leave"


OWNER_ONLY: Final = frozenset(
    {
        WorkspaceAction.MANAGE_BILLING,
        WorkspaceAction.DELETE_WORKSPACE,
        WorkspaceAction.EXPORT_WORKSPACE,
    }
)
ADMIN_ONLY: Final = frozenset(
    {
        WorkspaceAction.MANAGE_PEOPLE,
        WorkspaceAction.MANAGE_TEAMS,
        WorkspaceAction.EDIT_SETTINGS,
        WorkspaceAction.CONNECT_SOURCES,
        WorkspaceAction.READ_USAGE,
    }
)


@dataclass(frozen=True, slots=True)
class Actor:
    """The member acting, as their membership says in this transaction."""

    membership_id: UUID
    role: WorkspaceRole

    @property
    def manages(self) -> bool:
        """Owner or admin."""
        return self.role in MANAGING_ROLES


def may(actor: Actor, action: WorkspaceAction, *, members_can_invite: bool) -> bool:
    """Whether the actor may take an action on the workspace."""
    if action in OWNER_ONLY:
        return actor.role is WorkspaceRole.OWNER
    if action in ADMIN_ONLY:
        return actor.manages
    if action is WorkspaceAction.LEAVE:
        # Последний владелец не уходит: сначала передаёт владение (§7).
        return actor.role is not WorkspaceRole.OWNER
    # Приглашают админы, а при включённой настройке и участники; гость — никогда.
    return actor.manages or (members_can_invite and actor.role is WorkspaceRole.MEMBER)


def may_invite_as(actor: Actor, role: WorkspaceRole, *, members_can_invite: bool) -> bool:
    """Whether the actor may invite someone with this role; only admins invite admins."""
    if role not in ASSIGNABLE_ROLES:
        return False
    if not may(actor, WorkspaceAction.INVITE, members_can_invite=members_can_invite):
        return False
    return role is WorkspaceRole.MEMBER or actor.manages


def may_manage_member(actor: Actor, target_id: UUID, target_role: WorkspaceRole) -> bool:
    """Admins manage everyone except the owner and themselves."""
    return (
        actor.manages
        and target_role is not WorkspaceRole.OWNER
        and target_id != actor.membership_id
    )


def may_set_role(
    actor: Actor, target_id: UUID, target_role: WorkspaceRole, new_role: WorkspaceRole
) -> bool:
    """Whether the actor may give a member a new role; ownership moves only by transfer."""
    return new_role in ASSIGNABLE_ROLES and may_manage_member(actor, target_id, target_role)


@dataclass(frozen=True, slots=True)
class TeamChange:
    """The teams a change adds one member to, with their privacy; leaving is always allowed."""

    target_id: UUID
    target_role: WorkspaceRole
    added_private: tuple[bool, ...]


def may_change_teams(actor: Actor, change: TeamChange) -> bool:
    """Admins place anyone in any team; a member only themselves, joining only open teams."""
    if may_manage_member(actor, change.target_id, change.target_role):
        return True
    if change.target_id != actor.membership_id or actor.role is WorkspaceRole.GUEST:
        return False
    return not any(change.added_private)


def may_edit_project(actor: Actor, lead_id: UUID | None) -> bool:
    """A project's lead and admins edit or delete it."""
    return actor.manages or lead_id == actor.membership_id


def sees_team(actor: Actor, *, private: bool, in_team: bool) -> bool:
    """A private team is seen only by its members and admins (§7)."""
    return not private or in_team or actor.manages


def sees_invitation(actor: Actor, invited_by: UUID) -> bool:
    """An invitee's address is shown to admins and to whoever invited them."""
    return actor.manages or invited_by == actor.membership_id


def sees_activity(actor: Actor) -> bool:
    """When members were last active is shown to admins only."""
    return actor.manages
