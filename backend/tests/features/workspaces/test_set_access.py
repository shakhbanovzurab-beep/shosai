"""Changing a workspace row's access: who may, which grantees, its audit row and event (§7)."""

import uuid

import pytest

from shosai.core.kernel.errors import AppError
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.workspaces.application.access_policy import AccessScopeMismatchError
from shosai.features.workspaces.contracts import (
    AccessChange,
    AccessLevel,
    Grantee,
    GranteeKind,
    Viewer,
)
from tests.features.workspaces.probe_resources import NOTES
from tests.features.workspaces.test_access_policy import policy
from tests.harness.connections import Connection, fetch_rows, fetch_value
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot
from tests.support.isolation import Canon, canonical_world, write_world

ACCESS_OF_ROW = "SELECT access FROM probe_meetings WHERE id = %s"


async def canon_in(run_slot: RunSlot, home: Home) -> Canon:
    canon = canonical_world("meeting")
    await write_world(run_slot.claimed.connections[home], NOTES, canon.world)
    return canon


def seat(canon: Canon, name: str, org: str) -> uuid.UUID:
    return next(
        m.id
        for m in canon.world.members
        if m.user_id == canon.people[name] and m.org_id == canon.workspaces[org]
    )


def bobs_open_row(canon: Canon) -> uuid.UUID:
    return next(
        row.id
        for row in canon.world.rows
        if row.owner == canon.people["bob"] and row.access == "organization"
    )


async def change(
    homes: DatabaseAccess,
    where: tuple[Home, Canon],
    actor: str | None,
    level: AccessLevel,
    grantees: frozenset[Grantee] = frozenset(),
) -> None:
    """Bob's open row in workspace A gets a new level, asked for by `actor` (None: platform)."""
    home, canon = where
    org = canon.workspaces["a"]
    user = canon.people[actor] if actor else None
    viewer = Viewer(user) if user else None
    request = AccessChange(NOTES, bobs_open_row(canon), org, level, grantees, viewer)
    async with homes.transactions.begin(TenancyScope(home, user, org)) as session:
        await policy().set_access(session, request)


async def access_of(connection: Connection, canon: Canon) -> object:
    return await fetch_value(connection, ACCESS_OF_ROW, (bobs_open_row(canon),))


async def test_the_owner_narrows_a_row_to_one_member_with_its_audit_row_and_event(
    homes: DatabaseAccess, probe_resources: None, run_slot: RunSlot
) -> None:
    canon = await canon_in(run_slot, Home.RU)
    connection = run_slot.claimed.connections[Home.RU]
    carol = Grantee(GranteeKind.MEMBER, seat(canon, "carol", "a"))

    await change(homes, (Home.RU, canon), "bob", AccessLevel.SELECTED, frozenset({carol}))

    grants = await fetch_rows(
        connection,
        "SELECT grantee_id FROM resource_grants WHERE resource_id = %s",
        (bobs_open_row(canon),),
    )
    audit = await fetch_rows(
        connection, "SELECT action, actor_membership_id, value FROM org_audit_events"
    )
    events = await fetch_rows(connection, "SELECT event_type FROM outbox_messages")
    assert await access_of(connection, canon) == "selected"
    assert [g["grantee_id"] for g in grants] == [carol.id]
    assert [dict(a) for a in audit] == [
        {
            "action": "access_changed",
            "actor_membership_id": seat(canon, "bob", "a"),
            "value": "selected",
        }
    ]
    assert [e["event_type"] for e in events] == ["workspaces.access.changed"]


async def test_an_admin_who_sees_the_row_may_change_it_and_the_platform_always_may(
    homes: DatabaseAccess, probe_resources: None, run_slot: RunSlot
) -> None:
    canon = await canon_in(run_slot, Home.EU)

    await change(homes, (Home.EU, canon), "alice", AccessLevel.OWNER)
    narrowed = await access_of(run_slot.claimed.connections[Home.EU], canon)
    await change(homes, (Home.EU, canon), None, AccessLevel.ORGANIZATION)

    assert narrowed == "owner"
    assert await access_of(run_slot.claimed.connections[Home.EU], canon) == "organization"


@pytest.mark.parametrize("actor", ["carol", "dan", "erin", "frank", "stranger"])
async def test_who_may_not_manage_the_row_finds_no_row(
    homes: DatabaseAccess, probe_resources: None, run_slot: RunSlot, actor: str
) -> None:
    canon = await canon_in(run_slot, Home.RU)

    with pytest.raises(AppError, match="resource_not_found"):
        await change(homes, (Home.RU, canon), actor, AccessLevel.OWNER)


async def test_grantees_must_belong_to_the_workspace_and_fit_the_level(
    homes: DatabaseAccess, probe_resources: None, run_slot: RunSlot
) -> None:
    canon = await canon_in(run_slot, Home.EU)
    outsider = Grantee(GranteeKind.MEMBER, seat(canon, "frank", "b"))
    removed = Grantee(GranteeKind.MEMBER, seat(canon, "erin", "a"))
    ghost_team = Grantee(GranteeKind.TEAM, uuid.uuid4())
    carol = Grantee(GranteeKind.MEMBER, seat(canon, "carol", "a"))

    for level, grantees in (
        (AccessLevel.SELECTED, frozenset({outsider})),
        (AccessLevel.SELECTED, frozenset({removed})),
        (AccessLevel.SELECTED, frozenset({ghost_team})),
        (AccessLevel.SELECTED, frozenset()),
        (AccessLevel.ORGANIZATION, frozenset({carol})),
    ):
        with pytest.raises(AppError, match="grantees_invalid"):
            await change(homes, (Home.EU, canon), "bob", level, grantees)
    assert await access_of(run_slot.claimed.connections[Home.EU], canon) == "organization"


async def test_the_change_runs_in_its_workspace_transaction(
    homes: DatabaseAccess, probe_resources: None, run_slot: RunSlot
) -> None:
    canon = await canon_in(run_slot, Home.RU)
    org_a, org_b = canon.workspaces["a"], canon.workspaces["b"]
    request = AccessChange(NOTES, bobs_open_row(canon), org_a, AccessLevel.OWNER, frozenset(), None)
    scope = TenancyScope(Home.RU, None, org_b)

    async with homes.transactions.begin(scope) as session:
        with pytest.raises(AccessScopeMismatchError):
            await policy().set_access(session, request)

    assert await access_of(run_slot.claimed.connections[Home.RU], canon) == "organization"
