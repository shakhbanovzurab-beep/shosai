"""Random worlds for the policy's property test: small and dense, with every state the rules name.

One or two workspaces and up to ten rows make rows of the same workspace meet: a member
granted one row must not read the next one (a check that loses its correlation does).
"""

import uuid

from hypothesis import strategies as st

from shosai.features.workspaces.infrastructure.share_records import SHARE_RECORDS
from tests.support.access_model import (
    GrantRow,
    MemberRow,
    ResourceRow,
    ShareRow,
    WorkspaceRow,
    World,
)

ROLES = ("admin", "member", "guest")
STATES = ("active", "active", "hidden", "removed")


@st.composite
def worlds(draw: st.DrawFn, kind: str) -> tuple[World, list[uuid.UUID]]:
    """A world of one or two workspaces, four people and three to ten rows of `kind`."""
    people = [uuid.uuid4() for _ in range(4)]
    world = World()
    for _ in range(draw(st.integers(1, 2))):
        org = WorkspaceRow(uuid.uuid4(), draw(st.sampled_from(("active", "active", "suspended"))))
        world.workspaces.append(org)
        members = draw(st.permutations(people))[: draw(st.integers(1, 4))]
        for index, user in enumerate(members):
            role = "owner" if index == 0 else draw(st.sampled_from(ROLES))
            state = (
                draw(st.sampled_from(("active", "hidden")))
                if index == 0
                else draw(st.sampled_from(STATES))
            )
            world.members.append(MemberRow(uuid.uuid4(), org.id, user, role, state))
        seats = [m.id for m in world.members if m.org_id == org.id]
        for _ in range(draw(st.integers(0, 2))):
            world.teams[uuid.uuid4()] = (
                org.id,
                frozenset(draw(st.lists(st.sampled_from(seats), unique=True))),
            )
    for _ in range(draw(st.integers(3, 10))):
        _add_row(draw, world, kind, people)
    return world, people


def _grantees(draw: st.DrawFn, world: World, org_id: uuid.UUID) -> list[tuple[str, uuid.UUID]]:
    members = [("member", m.id) for m in world.members if m.org_id == org_id]
    teams = [("team", team) for team, (org, _) in world.teams.items() if org == org_id]
    return draw(st.lists(st.sampled_from(members + teams), unique=True, min_size=1, max_size=3))


def _add_row(draw: st.DrawFn, world: World, kind: str, people: list[uuid.UUID]) -> None:
    owner = draw(st.sampled_from(people))
    orgs = [w.id for w in world.workspaces]
    org = draw(st.none() | st.sampled_from(orgs))
    row_id = uuid.uuid4()
    if org is not None:
        access = draw(st.sampled_from(("owner", "selected", "selected", "organization")))
        world.rows.append(ResourceRow(row_id, kind, owner, org, access))
        if access == "selected":
            for grantee in _grantees(draw, world, org):
                world.grants.append(GrantRow(org, kind, row_id, *grantee))
        return
    world.rows.append(ResourceRow(row_id, kind, owner, None, None))
    records = SHARE_RECORDS.get(kind)
    seats = [m for m in world.members if m.user_id == owner]
    if records is None or not seats or not draw(st.booleans()):
        return
    seat = draw(st.sampled_from(seats))
    access = draw(st.sampled_from(("selected", "organization")))
    key = row_id if records.grant_key == records.resource else uuid.uuid4()
    world.shares.append(
        ShareRow(kind, row_id, seat.org_id, access, seat.id, records.grant_kind, key)
    )
    if access == "selected":
        for grantee in _grantees(draw, world, seat.org_id):
            world.grants.append(GrantRow(seat.org_id, records.grant_kind, key, *grantee))
