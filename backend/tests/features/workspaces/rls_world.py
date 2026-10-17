"""A small world of three workspaces, written by the tables' owner, for row-level security tests.

Person P belongs to A (as owner) and B (as member); C belongs to someone else. Each
workspace has one team. Rows are written over the migration role's direct connection, so
they exist whatever the policies say; the `homes` fixture empties the tables afterwards.
"""

import uuid
from dataclasses import dataclass, field

from tests.harness.connections import Connection


@dataclass(frozen=True, slots=True)
class World:
    """The ids of the world's workspaces, people, memberships and teams."""

    person: uuid.UUID = field(default_factory=uuid.uuid4)
    stranger: uuid.UUID = field(default_factory=uuid.uuid4)
    org_a: uuid.UUID = field(default_factory=uuid.uuid4)
    org_b: uuid.UUID = field(default_factory=uuid.uuid4)
    org_c: uuid.UUID = field(default_factory=uuid.uuid4)
    membership_a: uuid.UUID = field(default_factory=uuid.uuid4)
    membership_b: uuid.UUID = field(default_factory=uuid.uuid4)


async def add_workspace(connection: Connection, org_id: uuid.UUID, owner: uuid.UUID) -> uuid.UUID:
    """A workspace with its owner's membership and one team named after the slug."""
    owner_membership = uuid.uuid4()
    slug = f"w-{org_id.hex[:8]}"
    # Владелец обязан быть к коммиту: отложенный триггер проверяет это в конце транзакции.
    async with connection.transaction():
        await connection.execute(
            "INSERT INTO organizations (id, slug, name, created_by) VALUES (%s, %s, %s, %s)",
            (org_id, slug, slug, owner),
        )
        await connection.execute(
            "INSERT INTO memberships (id, org_id, user_id, role) VALUES (%s, %s, %s, 'owner')",
            (owner_membership, org_id, owner),
        )
        await connection.execute(
            "INSERT INTO teams (id, org_id, name, color) VALUES (%s, %s, %s, 'blue')",
            (uuid.uuid4(), org_id, slug),
        )
    return owner_membership


async def build_world(connection: Connection) -> World:
    """A: P owns it; B: P is a member; C: only the stranger."""
    world = World()
    await add_workspace(connection, world.org_a, world.person)
    await connection.execute(
        "UPDATE memberships SET id = %s WHERE org_id = %s",
        (world.membership_a, world.org_a),
    )
    await add_workspace(connection, world.org_b, world.stranger)
    await connection.execute(
        "INSERT INTO memberships (id, org_id, user_id, role) VALUES (%s, %s, %s, 'member')",
        (world.membership_b, world.org_b, world.person),
    )
    await add_workspace(connection, world.org_c, world.stranger)
    return world


def slug_of(org_id: uuid.UUID) -> str:
    """The slug and team name `add_workspace` gave a workspace."""
    return f"w-{org_id.hex[:8]}"


async def add_member(
    connection: Connection, org_id: uuid.UUID, user_id: uuid.UUID, role: str, days_ago: int
) -> uuid.UUID:
    """A membership that joined `days_ago` days ago; the earlier, the longer it stands."""
    membership = uuid.uuid4()
    await connection.execute(
        "INSERT INTO memberships (id, org_id, user_id, role, title, joined_at) "
        "VALUES (%s, %s, %s, %s, 'Engineer', now() - make_interval(days => %s))",
        (membership, org_id, user_id, role, days_ago),
    )
    return membership
