"""The model base: constraint names, the homes of a table, the application metadata."""

import pytest
from sqlalchemy import CheckConstraint, Column, Integer, MetaData, Table, Text, UniqueConstraint

from whisperer.composition.metadata import application_metadata, application_models
from whisperer.core.db.home_identity import HomeIdentity
from whisperer.core.db.model_base import (
    NAMING_CONVENTION,
    is_seeded_by_migration,
    metadata_for_home,
    table_homes,
    table_info,
)
from whisperer.core.kernel.homes import Home


def sample_metadata() -> MetaData:
    """A table for every home and one for the EU home only, as the directory is."""
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    Table("notes", metadata, Column("id", Integer, primary_key=True))
    Table(
        "directory_entries",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("email_hmac", Text),
        UniqueConstraint("email_hmac"),
        CheckConstraint("id > 0", name="positive"),
        info=table_info(homes=(Home.EU,)),
    )
    return metadata


def test_a_table_exists_in_every_home_unless_it_says_otherwise() -> None:
    tables = sample_metadata().tables

    assert table_homes(tables["notes"]) == frozenset(Home)
    assert table_homes(tables["directory_entries"]) == frozenset({Home.EU})


def test_the_metadata_of_a_home_has_only_its_tables() -> None:
    metadata = sample_metadata()

    assert set(metadata_for_home(metadata, Home.RU).tables) == {"notes"}
    assert set(metadata_for_home(metadata, Home.EU).tables) == {"notes", "directory_entries"}


def test_constraint_names_follow_the_convention() -> None:
    table = metadata_for_home(sample_metadata(), Home.EU).tables["directory_entries"]

    names = {constraint.name for constraint in table.constraints}

    assert names == {
        "pk_directory_entries",
        "uq_directory_entries_email_hmac",
        "ck_directory_entries_positive",
    }


def test_a_table_belongs_to_at_least_one_home() -> None:
    with pytest.raises(ValueError, match="хотя бы в одном доме"):
        table_info(homes=())


def test_the_application_metadata_has_exactly_the_listed_models() -> None:
    metadata = application_metadata()

    assert set(metadata.tables) == {model.__tablename__ for model in application_models()}
    assert metadata.naming_convention == NAMING_CONVENTION
    assert application_metadata() is not metadata


def test_the_home_identity_is_seeded_by_its_migration() -> None:
    table = application_metadata().tables[HomeIdentity.__tablename__]

    assert is_seeded_by_migration(table)
    assert table_homes(table) == frozenset(Home)
