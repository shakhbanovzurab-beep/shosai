"""Every table with a person's rows is declared once in the deletion registry (§14 rule 7)."""

from sqlalchemy import Column, ForeignKey, MetaData, Table, Uuid

from shosai.composition.account_data import account_data_problems
from shosai.composition.features import FEATURES, account_data_specs
from shosai.composition.metadata import application_metadata
from shosai.core.account_data.spec import AccountDataSpec, TableCoverage, Treatment


def fixture_metadata() -> MetaData:
    metadata = MetaData()
    Table("users", metadata, Column("id", Uuid, primary_key=True))
    Table("notes", metadata, Column("id", Uuid, primary_key=True), Column("user_id", Uuid))
    Table(
        "shares",
        metadata,
        Column("id", Uuid, primary_key=True),
        Column("owner", Uuid, ForeignKey("users.id")),
    )
    Table("prices", metadata, Column("id", Uuid, primary_key=True))
    return metadata


def test_the_application_tables_are_covered() -> None:
    problems = account_data_problems(application_metadata(FEATURES), account_data_specs(FEATURES))

    assert problems == []


def test_a_table_with_a_person_id_and_no_declaration_is_found() -> None:
    specs = [AccountDataSpec("notes", (TableCoverage("notes", Treatment.ERASE),))]

    problems = account_data_problems(fixture_metadata(), specs)

    assert problems == ["shares: строки человека без владельца в реестре удаления"]


def test_a_table_declared_twice_or_missing_is_found() -> None:
    erase_notes = (TableCoverage("notes", Treatment.ERASE),)
    specs = [
        AccountDataSpec("notes", (*erase_notes, TableCoverage("shares", Treatment.ERASE))),
        AccountDataSpec("archive", (*erase_notes, TableCoverage("ghosts", Treatment.ERASE))),
    ]

    problems = account_data_problems(fixture_metadata(), specs)

    assert problems == [
        "ghosts: объявлена archive, но такой таблицы нет",
        "notes: объявлена несколькими владельцами ['archive', 'notes']",
    ]
