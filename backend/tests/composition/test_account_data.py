"""Every table with a person's rows is declared once in the deletion registry (§14 rule 7)."""

from collections.abc import AsyncIterator, Mapping

import pytest
from sqlalchemy import Column, ForeignKey, MetaData, Table, Uuid

from shosai.composition.account_data import (
    account_data_problems,
    check_account_handlers,
)
from shosai.composition.features import FEATURES, account_data_specs
from shosai.composition.metadata import application_metadata
from shosai.core.account_data.handlers import (
    ACCOUNT_DATA_HANDLERS,
    AccountRef,
    ExportFile,
    handler_problems,
)
from shosai.core.account_data.spec import AccountDataSpec, TableCoverage, Treatment
from shosai.core.kernel.homes import Home
from shosai.core.ports.directory import PortDirectory


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


class Handler:
    """An erasure handler of one owner that erases nothing."""

    def __init__(self, owner: str) -> None:
        self._owner = owner

    @property
    def owner(self) -> str:
        return self._owner

    async def export(self, account: AccountRef) -> AsyncIterator[ExportFile]:
        yield ExportFile(f"{account.user_id}.jsonl", _empty())

    async def erase(self, account: AccountRef) -> None:
        del account

    async def copy(self, account: AccountRef, to_home: Home) -> None:
        del account, to_home

    async def manifest(self, account: AccountRef) -> Mapping[str, str]:
        return {str(account.user_id): ""}

    async def purge(self, account: AccountRef) -> None:
        del account

    async def remains(self, account: AccountRef) -> tuple[str, ...]:
        del account
        return ()


async def _empty() -> AsyncIterator[bytes]:
    yield b""


def test_every_owner_that_erases_has_one_handler_and_every_handler_an_owner() -> None:
    erasing = AccountDataSpec("notes", tables=(TableCoverage("notes", Treatment.ERASE),))
    kept = AccountDataSpec("money", tables=(TableCoverage("payments", Treatment.KEEP_BY_LAW),))
    files = AccountDataSpec("files", prefixes=("files/",))

    complete = handler_problems([erasing, kept, files], [Handler("notes"), Handler("files")])
    broken = handler_problems(
        [erasing, kept, files], [Handler("notes"), Handler("notes"), Handler("ghost")]
    )

    assert complete == []
    assert broken == [
        "files: стирает данные человека, но обработчиков 0, а не один",
        "ghost: обработчик стирания без объявления в реестре",
        "notes: стирает данные человека, но обработчиков 2, а не один",
    ]


def test_core_and_every_slice_of_the_platform_need_exactly_their_handlers() -> None:
    bound, missing = PortDirectory(), PortDirectory()
    bound.install(
        [
            ACCOUNT_DATA_HANDLERS.bind(Handler(owner))
            for owner in (
                "core",
                "identity",
                "workspaces",
                "billing",
                "files",
                "notes",
                "tasks",
                "agent",
            )
        ]
    )
    missing.install([ACCOUNT_DATA_HANDLERS.bind(Handler("core"))])

    check_account_handlers(account_data_specs(FEATURES), bound)
    with pytest.raises(RuntimeError, match="identity"):
        check_account_handlers(account_data_specs(FEATURES), missing)
