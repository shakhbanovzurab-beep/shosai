"""The run's schema and data in the claimed slot (ADR 0009, item 4).

The run upgrades both homes to the head before the first test and downgrades them to the
base at the end; every test leaves the application tables empty. The migration runner is
the production one, so every run also proves that each revision downgrades.
"""

from psycopg import sql

from tests.harness.connections import Connection, fetch_value
from tests.harness.slots import ClaimedSlot
from whisperer.composition.metadata import application_metadata
from whisperer.core.db.migrations import MigrationTarget, downgrade, upgrade
from whisperer.core.db.model_base import is_seeded_by_migration, metadata_for_home
from whisperer.core.kernel.homes import Home

BASE_REVISION = "base"
VERSION_TABLE = "alembic_version"
VERSION_TABLE_EXISTS_SQL = f"SELECT to_regclass('public.{VERSION_TABLE}') IS NOT NULL"


def migration_targets(claimed: ClaimedSlot) -> list[MigrationTarget]:
    """The slot's database in each home, RU first, as the migration runner takes them."""
    targets: list[MigrationTarget] = []
    for home in Home:
        home_targets = claimed.targets(home)
        targets.append(
            MigrationTarget(
                home=home,
                url=home_targets.migration.url(),
                application_role=home_targets.application.user,
            )
        )
    return targets


async def migrate_slot(claimed: ClaimedSlot) -> None:
    """Apply the whole history to both homes of the slot."""
    await upgrade(migration_targets(claimed), application_metadata())


async def unmigrate_slot(claimed: ClaimedSlot) -> None:
    """Run every downgrade in both homes, then drop the version table Alembic leaves behind."""
    await downgrade(migration_targets(claimed), application_metadata(), BASE_REVISION)
    for connection in claimed.connections.values():
        if await fetch_value(connection, VERSION_TABLE_EXISTS_SQL):
            await connection.execute(sql.SQL("DROP TABLE {}").format(sql.Identifier(VERSION_TABLE)))


def cleared_tables(home: Home) -> list[str]:
    """Application tables of a home that tests clear: all but those a migration fills."""
    metadata = metadata_for_home(application_metadata(), home)
    return [table.name for table in metadata.sorted_tables if not is_seeded_by_migration(table)]


async def clear_tables(connection: Connection, tables: list[str]) -> None:
    """Empty the tables in one statement; identities restart, dependants are emptied too."""
    if not tables:
        return
    names = sql.SQL(", ").join(sql.Identifier(table) for table in tables)
    await connection.execute(sql.SQL("TRUNCATE {} RESTART IDENTITY CASCADE").format(names))


async def clear_homes(claimed: ClaimedSlot) -> None:
    """Empty the application tables of both homes after a test."""
    for home, connection in claimed.connections.items():
        await clear_tables(connection, cleared_tables(home))
