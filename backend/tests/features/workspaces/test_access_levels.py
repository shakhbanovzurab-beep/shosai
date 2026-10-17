"""Access levels, grants and the cabinet's audiences (§7, ADR 0039 point 4)."""

from uuid import UUID, uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st

from shosai.features.workspaces.domain.access import (
    Access,
    AccessLevel,
    Audience,
    AudienceKind,
    Grantee,
    GranteeKind,
    MemberView,
    SharingDefault,
    access_for,
    audience_of,
    level_admits,
)
from shosai.features.workspaces.domain.roles import WorkspaceRole

ids = st.uuids()
grantees = st.builds(Grantee, st.sampled_from(GranteeKind), ids)
members = st.builds(MemberView, ids, st.sampled_from(WorkspaceRole), st.frozensets(ids, max_size=3))
audiences = st.one_of(
    st.just(Audience(AudienceKind.PARTICIPANTS)),
    st.just(Audience(AudienceKind.WORKSPACE)),
    ids.map(lambda team: Audience(AudienceKind.TEAM, team)),
)


@given(audiences, st.frozensets(ids, max_size=4))
def test_an_audience_survives_the_round_trip_through_its_level(
    audience: Audience, always: frozenset[UUID]
) -> None:
    assert audience_of(access_for(audience, always)) == audience


@given(audiences, st.frozensets(ids, min_size=1, max_size=4), members)
def test_the_people_a_resource_always_admits_read_it_at_every_audience(
    audience: Audience, always: frozenset[UUID], member: MemberView
) -> None:
    participant = MemberView(next(iter(always)), WorkspaceRole.MEMBER, member.team_ids)

    assert level_admits(access_for(audience, always), participant)


@given(st.frozensets(grantees, max_size=5), members)
def test_selected_admits_exactly_the_granted_member_or_their_teams(
    grants: frozenset[Grantee], member: MemberView
) -> None:
    expected = any(
        (grant.kind is GranteeKind.MEMBER and grant.id == member.membership_id)
        or (grant.kind is GranteeKind.TEAM and grant.id in member.team_ids)
        for grant in grants
    )

    assert level_admits(Access(AccessLevel.SELECTED, grants), member) is expected


@given(members)
def test_the_whole_workspace_admits_everyone_but_guests_and_owner_level_nobody(
    member: MemberView,
) -> None:
    assert level_admits(Access(AccessLevel.ORGANIZATION), member) is (
        member.role is not WorkspaceRole.GUEST
    )
    assert not level_admits(Access(AccessLevel.OWNER), member)


def test_admin_rights_do_not_widen_a_selected_row() -> None:
    admin = MemberView(uuid4(), WorkspaceRole.OWNER, frozenset())
    row = Access(AccessLevel.SELECTED, frozenset({Grantee(GranteeKind.MEMBER, uuid4())}))

    assert not level_admits(row, admin)


def test_a_row_only_its_owner_reads_has_no_audience() -> None:
    assert audience_of(Access(AccessLevel.OWNER)) is None


@pytest.mark.parametrize(
    ("kind", "team"), [(AudienceKind.TEAM, None), (AudienceKind.WORKSPACE, uuid4())]
)
def test_a_team_is_named_by_a_team_audience_and_only_by_it(
    kind: AudienceKind, team: UUID | None
) -> None:
    with pytest.raises(ValueError, match="team"):
        Audience(kind, team)


def test_a_private_default_shares_nothing_and_the_others_map_to_audiences() -> None:
    assert SharingDefault.PRIVATE.audience() is None
    assert SharingDefault.PARTICIPANTS.audience() == Audience(AudienceKind.PARTICIPANTS)
    assert SharingDefault.WORKSPACE.audience() == Audience(AudienceKind.WORKSPACE)
