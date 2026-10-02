"""Catalog fingerprint of a test database and its return to the prepared state (ADR 0009)."""

from dataclasses import dataclass
from typing import Self

from psycopg import sql

from tests.harness.connections import Connection, fetch_rows, load_sql

FINGERPRINT_SQL_FILE = "catalog_fingerprint.sql"
LEFTOVERS_SQL_FILE = "leftover_drop_statements.sql"
PREPARED_STATE_SQL_FILE = "prepared_state_statements.sql"


@dataclass(frozen=True, slots=True, order=True)
class CatalogEntry:
    """One catalog object: its kind, its name and everything that defines it."""

    kind: str
    identity: str
    detail: str

    def describe(self) -> str:
        """Line for a difference report."""
        label = f"{self.kind} {self.identity}"
        return f"{label}: {self.detail}" if self.detail else label


@dataclass(frozen=True, slots=True)
class CatalogFingerprint:
    """Every object of the database outside extensions, with its rights."""

    entries: frozenset[CatalogEntry]

    @classmethod
    async def take(cls, connection: Connection) -> Self:
        """Take the fingerprint inside the connection's current transaction."""
        rows = await fetch_rows(connection, load_sql(FINGERPRINT_SQL_FILE))
        return cls(
            entries=frozenset(
                CatalogEntry(kind=row["kind"], identity=row["identity"], detail=row["detail"])
                for row in rows
            )
        )

    def changes_since(self, reference: Self) -> list[str]:
        """Objects that appeared (`+`) and disappeared (`-`) compared with the reference."""
        added = sorted(self.entries - reference.entries)
        removed = sorted(reference.entries - self.entries)
        return [
            *(f"+ {entry.describe()}" for entry in added),
            *(f"- {entry.describe()}" for entry in removed),
        ]


async def restore_prepared_state(connection: Connection, application_role: str) -> list[str]:
    """Return the database to the state F3 prepares, in one transaction.

    Drops what a crashed run left behind and restores rights and settings that do
    not go away with objects. Returns the catalog changes it made; a clean database
    gives an empty list.
    """
    before = await CatalogFingerprint.take(connection)
    # Файл — доверенный текст харнесса; роль подставляется литералом с экранированием psycopg.
    prepared_state = sql.SQL(load_sql(PREPARED_STATE_SQL_FILE)).format(
        application_role=sql.Literal(application_role)
    )
    async with connection.transaction():
        for row in await fetch_rows(connection, load_sql(LEFTOVERS_SQL_FILE)):
            await connection.execute(row["statement"].encode())
        for row in await fetch_rows(connection, prepared_state):
            await connection.execute(row["statement"].encode())
    after = await CatalogFingerprint.take(connection)
    return after.changes_since(before)
