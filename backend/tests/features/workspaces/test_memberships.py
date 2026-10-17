"""A membership's life, the last-owner rule and succession (§7, ADR 0053 point 4)."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st

from shosai.features.workspaces.domain.memberships import (
    MembershipState,
    MembershipTransitionError,
    OwnershipTransferError,
    RosterChange,
    RosterEntry,
    apply_change,
    check_transition,
    has_owner,
    keeps_an_owner,
    ownership_transfer,
    successor,
)
from shosai.features.workspaces.domain.roles import WorkspaceRole

START = datetime(2026, 1, 1, tzinfo=UTC)
ALLOWED = {
    (MembershipState.ACTIVE, MembershipState.HIDDEN),
    (MembershipState.ACTIVE, MembershipState.REMOVED),
    (MembershipState.HIDDEN, MembershipState.ACTIVE),
    (MembershipState.HIDDEN, MembershipState.REMOVED),
    (MembershipState.REMOVED, MembershipState.ACTIVE),
}

entries = st.builds(
    RosterEntry,
    membership_id=st.uuids(),
    role=st.sampled_from(WorkspaceRole),
    state=st.sampled_from(MembershipState),
    joined_at=st.integers(0, 1000).map(lambda days: START + timedelta(days=days)),
)
rosters = st.lists(entries, min_size=1, max_size=8, unique_by=lambda entry: entry.membership_id)


def entry(
    role: WorkspaceRole, days: int, state: MembershipState = MembershipState.ACTIVE
) -> RosterEntry:
    return RosterEntry(uuid4(), role, state, START + timedelta(days=days))


@given(st.sampled_from(MembershipState), st.sampled_from(MembershipState))
def test_a_membership_moves_only_along_its_life(
    current: MembershipState, target: MembershipState
) -> None:
    if (current, target) in ALLOWED:
        check_transition(current, target)
    else:
        with pytest.raises(MembershipTransitionError):
            check_transition(current, target)


@given(rosters, st.data())
def test_an_accepted_change_never_leaves_a_workspace_without_an_owner(
    roster: list[RosterEntry], data: st.DataObject
) -> None:
    target = data.draw(st.sampled_from(roster))
    change = RosterChange(
        target.membership_id,
        role=data.draw(st.none() | st.sampled_from(WorkspaceRole)),
        state=data.draw(st.none() | st.sampled_from(MembershipState)),
    )

    after = [
        (change.role or e.role, change.state or e.state)
        if e.membership_id == change.membership_id
        else (e.role, e.state)
        for e in roster
    ]
    standing = {MembershipState.ACTIVE, MembershipState.HIDDEN}
    owner_left = any(role is WorkspaceRole.OWNER and state in standing for role, state in after)

    assert keeps_an_owner(roster, change) is owner_left
    assert has_owner(apply_change(roster, change)) is owner_left


def test_the_only_owner_cannot_leave_or_be_demoted_but_may_be_hidden() -> None:
    owner = entry(WorkspaceRole.OWNER, 0)
    roster = [owner, entry(WorkspaceRole.ADMIN, 1)]

    assert not keeps_an_owner(
        roster, RosterChange(owner.membership_id, state=MembershipState.REMOVED)
    )
    assert not keeps_an_owner(roster, RosterChange(owner.membership_id, role=WorkspaceRole.ADMIN))
    # Окно удаления аккаунта: владелец скрыт, но остаётся владельцем до стирания.
    assert keeps_an_owner(roster, RosterChange(owner.membership_id, state=MembershipState.HIDDEN))


def test_a_second_owner_lets_the_first_one_go() -> None:
    first, second = entry(WorkspaceRole.OWNER, 0), entry(WorkspaceRole.OWNER, 5)

    assert keeps_an_owner(
        [first, second], RosterChange(first.membership_id, state=MembershipState.REMOVED)
    )


def test_the_successor_is_the_longest_standing_admin_then_member() -> None:
    owner = entry(WorkspaceRole.OWNER, 0)
    old_member = entry(WorkspaceRole.MEMBER, 1)
    young_admin = entry(WorkspaceRole.ADMIN, 9)
    old_admin = entry(WorkspaceRole.ADMIN, 3)
    hidden_admin = entry(WorkspaceRole.ADMIN, 2, MembershipState.HIDDEN)
    guest = entry(WorkspaceRole.GUEST, 0)
    roster = [owner, old_member, young_admin, old_admin, hidden_admin, guest]

    assert successor(roster, owner.membership_id) == old_admin.membership_id
    assert successor([owner, old_member, guest], owner.membership_id) == old_member.membership_id
    assert successor([owner, guest, hidden_admin], owner.membership_id) is None


@given(rosters, st.data())
def test_the_successor_is_always_an_active_admin_or_member_other_than_the_leaver(
    roster: list[RosterEntry], data: st.DataObject
) -> None:
    leaving: UUID = data.draw(st.sampled_from(roster)).membership_id

    chosen = successor(roster, leaving)

    if chosen is not None:
        picked = next(entry for entry in roster if entry.membership_id == chosen)
        assert picked.membership_id != leaving
        assert picked.state is MembershipState.ACTIVE
        assert picked.role in {WorkspaceRole.ADMIN, WorkspaceRole.MEMBER}


def test_ownership_passes_to_an_active_member_and_the_old_owner_becomes_admin() -> None:
    owner, member = entry(WorkspaceRole.OWNER, 0), entry(WorkspaceRole.MEMBER, 1)

    changes = ownership_transfer([owner, member], member.membership_id)
    roster = [owner, member]
    for change in changes:
        roster = list(apply_change(roster, change))

    assert {(e.membership_id, e.role) for e in roster} == {
        (owner.membership_id, WorkspaceRole.ADMIN),
        (member.membership_id, WorkspaceRole.OWNER),
    }


@pytest.mark.parametrize(
    ("role", "state"),
    [
        (WorkspaceRole.OWNER, MembershipState.ACTIVE),
        (WorkspaceRole.GUEST, MembershipState.ACTIVE),
        (WorkspaceRole.MEMBER, MembershipState.HIDDEN),
        (WorkspaceRole.ADMIN, MembershipState.REMOVED),
    ],
)
def test_ownership_never_passes_to_an_owner_a_guest_or_someone_absent(
    role: WorkspaceRole, state: MembershipState
) -> None:
    target = entry(role, 1, state)

    with pytest.raises(OwnershipTransferError):
        ownership_transfer([entry(WorkspaceRole.OWNER, 0), target], target.membership_id)


def test_ownership_cannot_pass_to_a_stranger() -> None:
    with pytest.raises(OwnershipTransferError):
        ownership_transfer([entry(WorkspaceRole.OWNER, 0)], uuid4())
