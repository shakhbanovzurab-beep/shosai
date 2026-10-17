"""The permission matrix of a workspace: the cabinet's `roles.ts`, held by the server."""

from uuid import UUID, uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st

from shosai.features.workspaces.domain.roles import (
    Actor,
    TeamChange,
    WorkspaceAction,
    WorkspaceRole,
    may,
    may_change_teams,
    may_edit_project,
    may_invite_as,
    may_manage_member,
    may_set_role,
    sees_activity,
    sees_invitation,
    sees_team,
)

roles = st.sampled_from(WorkspaceRole)
actions = st.sampled_from(WorkspaceAction)
OWNER, ADMIN = WorkspaceRole.OWNER, WorkspaceRole.ADMIN
MEMBER, GUEST = WorkspaceRole.MEMBER, WorkspaceRole.GUEST
MANAGERS = frozenset({OWNER, ADMIN})
# Кто может действие при выключенной настройке «участники приглашают» — как в roles.ts.
MATRIX: dict[WorkspaceAction, frozenset[WorkspaceRole]] = {
    WorkspaceAction.INVITE: MANAGERS,
    WorkspaceAction.MANAGE_PEOPLE: MANAGERS,
    WorkspaceAction.MANAGE_TEAMS: MANAGERS,
    WorkspaceAction.EDIT_SETTINGS: MANAGERS,
    WorkspaceAction.CONNECT_SOURCES: MANAGERS,
    WorkspaceAction.READ_USAGE: MANAGERS,
    WorkspaceAction.MANAGE_BILLING: frozenset({OWNER}),
    WorkspaceAction.DELETE_WORKSPACE: frozenset({OWNER}),
    WorkspaceAction.EXPORT_WORKSPACE: frozenset({OWNER}),
    WorkspaceAction.LEAVE: frozenset({ADMIN, MEMBER, GUEST}),
}


def actor(role: WorkspaceRole, membership_id: UUID | None = None) -> Actor:
    return Actor(membership_id or uuid4(), role)


def test_the_matrix_names_every_action() -> None:
    assert set(MATRIX) == set(WorkspaceAction)


@given(role=roles, action=actions)
def test_each_role_may_exactly_what_the_cabinet_shows(
    role: WorkspaceRole, action: WorkspaceAction
) -> None:
    assert may(actor(role), action, members_can_invite=False) is (role in MATRIX[action])


@given(role=roles, action=actions)
def test_members_can_invite_widens_only_inviting_and_only_to_members(
    role: WorkspaceRole, action: WorkspaceAction
) -> None:
    allowed = may(actor(role), action, members_can_invite=True)

    if action is WorkspaceAction.INVITE:
        assert allowed is (role is not GUEST)
    else:
        assert allowed is may(actor(role), action, members_can_invite=False)


@given(inviter=roles, invited=roles, members_can_invite=st.booleans())
def test_only_admins_invite_admins_and_nobody_invites_an_owner_or_guest(
    inviter: WorkspaceRole, invited: WorkspaceRole, *, members_can_invite: bool
) -> None:
    who = actor(inviter)
    allowed = may_invite_as(who, invited, members_can_invite=members_can_invite)

    if invited in {OWNER, GUEST}:
        assert not allowed
    elif invited is ADMIN:
        assert allowed is (inviter in MANAGERS)
    else:
        assert allowed is may(who, WorkspaceAction.INVITE, members_can_invite=members_can_invite)


@given(who=roles, target=roles, self_target=st.booleans())
def test_nobody_manages_the_owner_or_themselves(
    who: WorkspaceRole, target: WorkspaceRole, *, self_target: bool
) -> None:
    me = actor(who)
    target_id = me.membership_id if self_target else uuid4()

    allowed = may_manage_member(me, target_id, target)

    assert allowed is (who in MANAGERS and target is not OWNER and not self_target)


@given(who=roles, target=roles, new_role=roles)
def test_a_role_change_never_makes_an_owner_or_a_guest(
    who: WorkspaceRole, target: WorkspaceRole, new_role: WorkspaceRole
) -> None:
    me = actor(who)

    allowed = may_set_role(me, uuid4(), target, new_role)

    if new_role in {OWNER, GUEST}:
        assert not allowed
    else:
        assert allowed is may_manage_member(me, uuid4(), target)


@given(added_private=st.lists(st.booleans(), max_size=4))
def test_a_member_joins_only_open_teams_and_only_for_themselves(added_private: list[bool]) -> None:
    me = actor(MEMBER)
    own = TeamChange(me.membership_id, MEMBER, tuple(added_private))
    others = TeamChange(uuid4(), MEMBER, tuple(added_private))

    assert may_change_teams(me, own) is (not any(added_private))
    assert not may_change_teams(me, others)
    assert may_change_teams(actor(ADMIN), others)


def test_a_guest_changes_no_teams_even_their_own() -> None:
    guest = actor(GUEST)

    assert not may_change_teams(guest, TeamChange(guest.membership_id, GUEST, ()))


@pytest.mark.parametrize(
    ("role", "lead", "allowed"),
    [(ADMIN, False, True), (MEMBER, True, True), (MEMBER, False, False)],
)
def test_a_project_is_edited_by_its_lead_and_admins(
    role: WorkspaceRole, *, lead: bool, allowed: bool
) -> None:
    me = actor(role)

    assert may_edit_project(me, me.membership_id if lead else uuid4()) is allowed
    assert not may_edit_project(actor(MEMBER), None)


@given(role=roles, private=st.booleans(), in_team=st.booleans())
def test_a_private_team_shows_to_its_members_and_admins_only(
    role: WorkspaceRole, *, private: bool, in_team: bool
) -> None:
    assert sees_team(actor(role), private=private, in_team=in_team) is (
        not private or in_team or role in MANAGERS
    )


@given(role=roles, own=st.booleans())
def test_invitation_addresses_and_activity_stay_with_who_manages(
    role: WorkspaceRole, *, own: bool
) -> None:
    me = actor(role)

    assert sees_invitation(me, me.membership_id if own else uuid4()) is (own or role in MANAGERS)
    assert sees_activity(me) is (role in MANAGERS)
