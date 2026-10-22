"""The isolation kit: every read path of a shareable resource is checked against §7 (§14 rule 12).

A slice writes its resource's rows through `write_world` and checks a read path with
`assert_isolated`: the kit builds the canonical world — two workspaces, a member of both,
a guest, a private team, a removed member, a hidden owner, personal rows shared and not —
and compares what the read path returns to each person with the reference model. Mark
the test `@pytest.mark.isolation(resource="<kind>")`; the gate refuses a declared
resource without one.

A resource with a parent or a named reader (ADR 0059) is checked in a world that also holds
its parent kind's rows, written to the parent's own table with its own columns
(`parents`), and rows naming readers; `extra` may compute a row's other columns from it.
"""

import uuid
from collections.abc import Awaitable, Callable, Mapping

from psycopg import sql

from shosai.core.access.shareable import ShareableResource
from shosai.features.workspaces.contracts import Viewer
from tests.harness.connections import Connection
from tests.support.access_model import ResourceRow, ShareRow, World, readable
from tests.support.isolation_world import Canon, canonical_world

__all__ = ["Canon", "assert_isolated", "canonical_world", "write_world"]

type ReadPath = Callable[[Viewer], Awaitable[set[uuid.UUID]]]
# Остальные колонки строки: одни для всех или по самой строке (задаче встречи — её источник).
type Extra = Mapping[str, object] | Callable[[ResourceRow], Mapping[str, object]]
# Ресурсы родителей по виду, с их обязательными колонками.
type Parents = Mapping[str, tuple[ShareableResource, Mapping[str, object]]]


async def write_world(
    connection: Connection,
    resource: ShareableResource,
    world: World,
    extra: Extra | None = None,
    parents: Parents | None = None,
) -> None:
    """Write the world in one transaction of the tables' owner; `extra` fills other columns.

    Rows of another kind go to their parent resource's table with its columns.
    """
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
            if parents and row.kind in parents:
                parent, columns = parents[row.kind]
                await _insert_row(connection, parent, row, columns)
            else:
                await _insert_row(connection, resource, row, _columns_of(row, extra))
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


def _columns_of(row: ResourceRow, extra: Extra | None) -> Mapping[str, object]:
    """The other columns of a row: the same for all, or computed from the row."""
    if extra is None:
        return {}
    if isinstance(extra, Mapping):
        return extra
    computed: Callable[[ResourceRow], Mapping[str, object]] = extra
    return computed(row)


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
    if resource.reader is not None:
        values[resource.reader] = row.reader
    if resource.parent is not None:
        values[resource.parent[1]] = row.parent
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


async def assert_isolated(
    connection: Connection,
    resource: ShareableResource,
    read_path: ReadPath,
    extra: Extra | None = None,
    parents: Parents | None = None,
) -> Canon:
    """Write the canonical world and check that the read path shows each person what §7 allows."""
    parent_kind = resource.parent[0] if resource.parent is not None else None
    canon = canonical_world(
        resource.kind, parent_kind=parent_kind, reader=resource.reader is not None
    )
    await write_world(connection, resource, canon.world, extra, parents)
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
        f"{':reader ' + names[row.reader] if row.reader else ''}"
        f"{':child' if row.parent else ''}"
        for row in canon.world.rows
        if row.id in ids
    )
