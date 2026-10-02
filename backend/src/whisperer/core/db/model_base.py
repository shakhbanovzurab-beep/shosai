"""The declarative base of every table and the homes a table exists in (ADR 0010).

Constraint names follow one convention, so a migration can name the constraint it drops.
A table exists in every home unless it declares otherwise: the directory, the platform
tables and the telemetry without an account exist only in the EU home, and code that
reads them names `Home.EU` explicitly.
"""

from collections.abc import Collection
from typing import Final

from sqlalchemy import MetaData, Table
from sqlalchemy.orm import DeclarativeBase

from whisperer.core.kernel.homes import Home

NAMING_CONVENTION: Final = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
HOMES_INFO_KEY: Final = "homes"
SEEDED_INFO_KEY: Final = "seeded_by_migration"


class ModelBase(DeclarativeBase):
    """Base class of the ORM models of every slice."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def table_info(
    *, homes: tuple[Home, ...] = tuple(Home), seeded_by_migration: bool = False
) -> dict[str, object]:
    """`info` of a table for `__table_args__`: its homes, and whether a migration writes its rows.

    Tests clear every table between themselves except those a migration fills.
    """
    if not homes:
        message = "таблица существует хотя бы в одном доме"
        raise ValueError(message)
    return {HOMES_INFO_KEY: homes, SEEDED_INFO_KEY: seeded_by_migration}


def table_homes(table: Table) -> frozenset[Home]:
    """The homes whose schema has the table; every home unless the table says otherwise."""
    homes: Collection[Home] = table.info.get(HOMES_INFO_KEY, tuple(Home))
    return frozenset(homes)


def is_seeded_by_migration(table: Table) -> bool:
    """The table's rows come from a migration, not from the application."""
    return bool(table.info.get(SEEDED_INFO_KEY, False))


def metadata_for_home(metadata: MetaData, home: Home) -> MetaData:
    """A copy of the metadata with only the tables that exist in the home."""
    scoped = MetaData(naming_convention=metadata.naming_convention)
    for table in metadata.sorted_tables:
        if home in table_homes(table):
            table.to_metadata(scoped)
    return scoped
