"""The isolation kit: every read path of a shareable resource is checked against §7 (§14 rule 12).

A slice writes its resource's rows through `write_world` and checks a read path with
`assert_isolated`: the kit builds the canonical world — two workspaces, a member of both,
a guest, a private team, a removed member, a hidden owner, personal rows shared and not —
and compares what the read path returns to each person with the reference model. Mark
the test `@pytest.mark.isolation(resource="<kind>")`; the gate refuses a declared
resource without one.
"""

import uuid
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field

from psycopg import sql

from shosai.core.access.shareable import ShareableResource
from shosai.features.workspaces.contracts import Viewer
from shosai.features.workspaces.infrastructure.share_records import SHARE_RECORDS
from tests.harness.connections import Connection
from tests.support.access_model import (
    GrantRow,
    MemberRow,
    ResourceRow,
    ShareRow,
    WorkspaceRow,
    World,
    readable,
)

type ReadPath = Callable[[Viewer], Awaitable[set[uuid.UUID]]]


async def write_world(
    connection: Connection,
    resource: ShareableResource,
    world: World,
    extra: Mapping[str, object] | None = None,
) -> None:
    """Write the world in one transaction of the tables' owner; `extra` fills other columns."""
    async with connection.transaction():
        for workspace in world.workspaces:
            await connection.execute(
                "INSERT INTO organizations (id, slug, name, created_by, state, suspended_at) "
                "VALUES (%s, %s, 'w', %s, %s, CASE WHEN %s = 'suspended' THEN now() END)",
                (
                    workspace.id,
                    f"w-{workspace.id.hex[:12]}",
                    uuid.uuid4(),
                    workspace.state,
                    workspace.state,
                ),
            )
        for member in world.members:
            removed = member.state == "removed"
            await connection.execute(
                "INSERT INTO memberships"
                " (id, org_id, user_id, role, state, removed_at, removal_reason)"
                " VALUES (%s, %s, %s, %s, %s,"
                " CASE WHEN %s THEN now() END, CASE WHEN %s THEN 'left' END)",
                (
                    member.id,
                    member.org_id,
                    member.user_id,
                    member.role,
                    member.state,
                    removed,
                    removed,
                ),
            )
        for team, (org_id, people) in world.teams.items():
            await connection.execute(
                "INSERT INTO teams (id, org_id, name, color, private)"
                " VALUES (%s, %s, 't', 'sky', true)",
                (team, org_id),
            )
            for person in people:
                await connection.execute(
                    "INSERT INTO team_members (team_id, membership_id, org_id) VALUES (%s, %s, %s)",
                    (team, person, org_id),
                )
        for row in world.rows:
            await _insert_row(connection, resource, row, extra or {})
        for share in world.shares:
            await _insert_share(connection, share)
        for grant in world.grants:
            await connection.execute(
                "INSERT INTO resource_grants"
                " (org_id, resource_kind, resource_id, grantee_kind, grantee_id)"
                " VALUES (%s, %s, %s, %s, %s)",
                (
                    grant.org_id,
                    grant.resource_kind,
                    grant.resource_id,
                    grant.grantee_kind,
                    grant.grantee_id,
                ),
            )


async def _insert_row(
    connection: Connection,
    resource: ShareableResource,
    row: ResourceRow,
    extra: Mapping[str, object],
) -> None:
    values = {
        resource.id: row.id,
        resource.owner: row.owner,
        resource.org: row.org_id,
        resource.access: row.access,
        **extra,
    }
    statement = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
        sql.Identifier(resource.table.name),
        sql.SQL(", ").join(sql.Identifier(name) for name in values),
        sql.SQL(", ").join(sql.Placeholder() for _ in values),
    )
    await connection.execute(statement, tuple(values.values()))


async def _insert_share(connection: Connection, share: ShareRow) -> None:
    if share.kind == "meeting":
        await connection.execute(
            "INSERT INTO workspace_meeting_shares"
            " (session_id, org_id, shared_by_membership_id, access) VALUES (%s, %s, %s, %s)",
            (share.resource_id, share.org_id, share.sharer, share.access),
        )
        return
    await connection.execute(
        "INSERT INTO workspace_knowledge_items"
        " (id, org_id, source_kind, file_id, access, added_by_membership_id)"
        " VALUES (%s, %s, 'personal', %s, %s, %s)",
        (share.grant_key, share.org_id, share.resource_id, share.access, share.sharer),
    )


@dataclass(slots=True)
class Canon:
    """The canonical world's people, so a test can name who should see what."""

    world: World = field(default_factory=World)
    people: dict[str, uuid.UUID] = field(default_factory=dict)
    workspaces: dict[str, uuid.UUID] = field(default_factory=dict)


def canonical_world(kind: str) -> Canon:
    """Two workspaces and seven people covering every rule of §7 for one resource kind."""
    canon = Canon()
    world, people = canon.world, canon.people
    org_a, org_b = uuid.uuid4(), uuid.uuid4()
    canon.workspaces.update(a=org_a, b=org_b)
    world.workspaces += [WorkspaceRow(org_a, "active"), WorkspaceRow(org_b, "active")]
    seats: dict[tuple[str, uuid.UUID], uuid.UUID] = {}
    for name, org, role, state in (
        ("alice", org_a, "owner", "active"),
        ("bob", org_a, "member", "active"),
        ("carol", org_a, "member", "active"),
        ("carol", org_b, "admin", "active"),
        ("dan", org_a, "guest", "active"),
        ("erin", org_a, "member", "removed"),
        ("gina", org_a, "owner", "hidden"),
        ("frank", org_b, "owner", "active"),
    ):
        people.setdefault(name, uuid.uuid4())
        seats[name, org] = uuid.uuid4()
        world.members.append(MemberRow(seats[name, org], org, people[name], role, state))
    people["stranger"] = uuid.uuid4()
    team = uuid.uuid4()
    world.teams[team] = (org_a, frozenset({seats["bob", org_a], seats["erin", org_a]}))

    def row(owner: str, org: uuid.UUID | None, access: str | None) -> uuid.UUID:
        row_id = uuid.uuid4()
        world.rows.append(ResourceRow(row_id, kind, people[owner], org, access))
        return row_id

    def grant(org: uuid.UUID, key: tuple[str, uuid.UUID], grantee: tuple[str, uuid.UUID]) -> None:
        world.grants.append(GrantRow(org, key[0], key[1], grantee[0], grantee[1]))

    row("bob", org_a, "organization")
    row("bob", org_a, "owner")
    grant(org_a, (kind, row("alice", org_a, "selected")), ("team", team))
    grant(org_a, (kind, row("alice", org_a, "selected")), ("member", seats["carol", org_a]))
    row("erin", org_a, "organization")
    row("frank", org_b, "organization")
    row("alice", None, None)
    records = SHARE_RECORDS.get(kind)
    if records is not None:
        for owner, org, access, grantee in (
            ("alice", org_a, "organization", None),
            ("gina", org_a, "organization", None),
            ("carol", org_b, "selected", ("member", seats["frank", org_b])),
            ("erin", org_a, "organization", None),
        ):
            shared = row(owner, None, None)
            # Гранты встречи — под её id, гранты файла — под id элемента знаний.
            key = shared if records.grant_key == records.resource else uuid.uuid4()
            share = ShareRow(kind, shared, org, access, seats[owner, org], records.grant_kind, key)
            world.shares.append(share)
            if grantee is not None:
                grant(org, (records.grant_kind, key), grantee)
    return canon


async def assert_isolated(
    connection: Connection,
    resource: ShareableResource,
    read_path: ReadPath,
    extra: Mapping[str, object] | None = None,
) -> Canon:
    """Write the canonical world and check that the read path shows each person what §7 allows."""
    canon = canonical_world(resource.kind)
    await write_world(connection, resource, canon.world, extra)
    for name, user_id in canon.people.items():
        expected = readable(canon.world, resource.kind, user_id)
        seen = await read_path(Viewer(user_id))
        extra_rows, missing = _describe(canon, seen - expected), _describe(canon, expected - seen)
        assert seen == expected, f"{resource.kind}: {name} also sees {extra_rows}, misses {missing}"
    return canon


def _describe(canon: Canon, ids: set[uuid.UUID]) -> list[str]:
    """Rows by owner, workspace and level, so a failure says which rule broke."""
    names = {user_id: name for name, user_id in canon.people.items()}
    labels = {org_id: label for label, org_id in canon.workspaces.items()}
    shared = {share.resource_id: labels[share.org_id] for share in canon.world.shares}
    return sorted(
        f"{names[row.owner]}:{labels.get(row.org_id, 'personal') if row.org_id else 'personal'}"
        f":{row.access or 'shared to ' + shared.get(row.id, 'nobody')}"
        for row in canon.world.rows
        if row.id in ids
    )
