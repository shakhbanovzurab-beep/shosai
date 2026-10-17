"""What workspaces holds of a person, exported, erased and kept from moving (ADR 0053 point 4)."""

import json
import uuid

import pytest

from shosai.core.account_data.handlers import AccountRef
from shosai.core.events.catalog import EventTypes
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.workspaces.application.account_data import (
    MembershipBlocksTransferError,
    WorkspacesAccountData,
)
from shosai.features.workspaces.infrastructure.audit_log import WorkspaceAuditLog
from shosai.features.workspaces.infrastructure.membership_reader import MembershipDirectory
from shosai.features.workspaces.module import WORKSPACES
from tests.features.workspaces.rls_world import add_member, add_workspace, build_world
from tests.harness.connections import Connection, fetch_rows, fetch_value
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot

COUNTS = {
    "team_members": "SELECT count(*) FROM team_members",
    "workspace_meeting_shares": "SELECT count(*) FROM workspace_meeting_shares",
    "resource_grants": "SELECT count(*) FROM resource_grants",
}


def handler(homes: DatabaseAccess) -> WorkspacesAccountData:
    outbox = EventOutbox(EventTypes(list(WORKSPACES.events)))
    return WorkspacesAccountData(homes.transactions, outbox, WorkspaceAuditLog())


async def events(connection: Connection) -> list[tuple[str, dict[str, object]]]:
    rows = await fetch_rows(
        connection, "SELECT event_type, payload FROM outbox_messages ORDER BY id"
    )
    return [(row["event_type"], row["payload"]) for row in rows]


async def membership(connection: Connection, membership_id: uuid.UUID) -> dict[str, object]:
    rows = await fetch_rows(
        connection,
        "SELECT role, state, title, removal_reason FROM memberships WHERE id = %s",
        (membership_id,),
    )
    return dict(rows[0])


async def test_a_member_leaves_with_their_shares_teams_and_grants(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    connection = run_slot.claimed.connections[Home.RU]
    world = await build_world(connection)
    team = await fetch_value(connection, "SELECT id FROM teams WHERE org_id = %s", (world.org_b,))
    session_id = uuid.uuid4()
    for statement, params in (
        ("UPDATE memberships SET title = 'Analyst' WHERE id = %s", (world.membership_b,)),
        (
            "INSERT INTO team_members (team_id, membership_id, org_id) VALUES (%s, %s, %s)",
            (team, world.membership_b, world.org_b),
        ),
        ("UPDATE teams SET lead_membership_id = %s WHERE id = %s", (world.membership_b, team)),
        (
            "INSERT INTO workspace_meeting_shares (session_id, org_id, shared_by_membership_id,"
            " access) VALUES (%s, %s, %s, 'selected')",
            (session_id, world.org_b, world.membership_b),
        ),
        (
            "INSERT INTO resource_grants (org_id, resource_kind, resource_id, grantee_kind,"
            " grantee_id) VALUES (%s, 'meeting', %s, 'team', %s)",
            (world.org_b, session_id, team),
        ),
    ):
        await connection.execute(statement, params)
    account = AccountRef(world.person, Home.RU)

    await handler(homes).erase(AccountRef(world.person, Home.RU))
    left = await membership(connection, world.membership_b)
    kept = {table: await fetch_value(connection, query) for table, query in COUNTS.items()}
    lead = await fetch_value(
        connection, "SELECT lead_membership_id FROM teams WHERE id = %s", (team,)
    )
    published = await events(connection)

    assert left == {
        "role": "member",
        "state": "removed",
        "title": None,
        "removal_reason": "account_erased",
    }
    assert kept == {"team_members": 0, "workspace_meeting_shares": 0, "resource_grants": 0}
    assert lead is None
    removed = [payload for kind, payload in published if kind == "workspaces.member.removed"]
    assert {payload["org_id"] for payload in removed} == {str(world.org_b)}
    assert removed[0]["successor_user_id"] == str(world.stranger)
    assert await handler(homes).remains(account) == ()


async def test_the_only_owner_is_succeeded_by_the_longest_standing_admin(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    connection = run_slot.claimed.connections[Home.EU]
    org, owner = uuid.uuid4(), uuid.uuid4()
    await add_workspace(connection, org, owner)
    old_member = await add_member(connection, org, uuid.uuid4(), "member", 30)
    young_admin = await add_member(connection, org, uuid.uuid4(), "admin", 1)
    old_admin = await add_member(connection, org, uuid.uuid4(), "admin", 10)

    await handler(homes).erase(AccountRef(owner, Home.EU))

    assert (await membership(connection, old_admin))["role"] == "owner"
    assert (await membership(connection, young_admin))["role"] == "admin"
    assert (await membership(connection, old_member))["role"] == "member"
    audit = await fetch_rows(connection, "SELECT action FROM org_audit_events ORDER BY action")
    assert [row["action"] for row in audit] == ["member_removed", "owner_transferred"]


async def test_a_workspace_nobody_else_belongs_to_goes_with_the_account(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    connection = run_slot.claimed.connections[Home.RU]
    org, owner = uuid.uuid4(), uuid.uuid4()
    await add_workspace(connection, org, owner)

    await handler(homes).erase(AccountRef(owner, Home.RU))

    assert await fetch_value(connection, "SELECT count(*) FROM organizations") == 0
    assert await fetch_value(connection, "SELECT count(*) FROM teams") == 0
    assert [kind for kind, _ in await events(connection)] == ["workspaces.workspace.deleted"]


async def test_a_second_erasure_changes_nothing(homes: DatabaseAccess, run_slot: RunSlot) -> None:
    connection = run_slot.claimed.connections[Home.EU]
    world = await build_world(connection)
    account = AccountRef(world.person, Home.EU)

    await handler(homes).erase(account)
    first = await events(connection)
    await handler(homes).erase(account)

    assert await events(connection) == first
    assert await handler(homes).remains(account) == ()


async def test_the_export_holds_every_membership_and_no_one_elses(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    world = await build_world(run_slot.claimed.connections[Home.RU])

    files = [item async for item in handler(homes).export(AccountRef(world.person, Home.RU))]
    lines = [
        json.loads(line)
        for item in files
        async for chunk in item.chunks
        for line in chunk.splitlines()
    ]

    assert [item.name for item in files] == ["memberships.jsonl"]
    assert {line["org_id"] for line in lines} == {str(world.org_a), str(world.org_b)}
    assert {line["role"] for line in lines} == {"owner", "member"}


async def test_a_member_does_not_move_and_a_former_member_moves_nothing(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    world = await build_world(run_slot.claimed.connections[Home.RU])
    account = AccountRef(world.person, Home.RU)

    with pytest.raises(MembershipBlocksTransferError):
        await handler(homes).copy(account, Home.EU)
    await handler(homes).erase(account)
    await handler(homes).copy(account, Home.EU)

    assert await handler(homes).manifest(account) == {}


async def test_the_reader_names_active_memberships_and_counts_hidden_ones_as_held(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    connection = run_slot.claimed.connections[Home.EU]
    world = await build_world(connection)
    reader = MembershipDirectory()
    scope = TenancyScope(Home.EU, world.person)

    async with homes.transactions.begin(scope, read_only=True) as session:
        active = await reader.active(session, world.person)
    await connection.execute(
        "UPDATE memberships SET state = 'hidden' WHERE user_id = %s", (world.person,)
    )
    async with homes.transactions.begin(scope, read_only=True) as session:
        hidden_active = await reader.active(session, world.person)
        hidden_held = await reader.has_memberships(session, world.person)
    async with homes.transactions.begin(TenancyScope(Home.EU, uuid.uuid4())) as session:
        stranger_held = await reader.has_memberships(session, world.person)

    assert {(item.org_id, item.role.value) for item in active} == {
        (world.org_a, "owner"),
        (world.org_b, "member"),
    }
    assert hidden_active == ()
    assert hidden_held is True
    # Чужие членства человек не видит: строки чужого человека скрыты политикой.
    assert stranger_held is False
