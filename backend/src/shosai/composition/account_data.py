"""Coverage of the export and deletion registry over the application's tables (§14 rule 7).

A table holds a person's rows when it has a `user_id` column or a foreign key to `users`.
Each such table is declared by exactly one owner (core or a slice) with its treatment,
and every declared table exists; a test runs this over the application metadata, so a
slice cannot add personal rows that deletion would miss (ADR 0045 point 7).
"""

from collections.abc import Sequence
from typing import Any

from sqlalchemy import MetaData, Table

from shosai.core.account_data.handlers import ACCOUNT_DATA_HANDLERS, handler_problems
from shosai.core.account_data.spec import AccountDataSpec
from shosai.core.db.transactions import HomeTransactions
from shosai.core.email.account_data import CoreAccountData
from shosai.core.ports.directory import PortDirectory
from shosai.core.ports.keys import PortBinding

PERSON_COLUMN = "user_id"
ACCOUNTS_TABLE = "users"


def account_data_problems(metadata: MetaData, specs: Sequence[AccountDataSpec]) -> list[str]:
    """Every gap and overlap between the tables with a person's rows and the declarations."""
    owners: dict[str, list[str]] = {}
    for spec in specs:
        for coverage in spec.tables:
            owners.setdefault(coverage.table, []).append(spec.owner)
    problems = [
        f"{table.name}: строки человека без владельца в реестре удаления"
        for table in metadata.tables.values()
        if holds_person(table) and table.name not in owners
    ]
    for name, declared_by in owners.items():
        if len(declared_by) > 1:
            problems.append(f"{name}: объявлена несколькими владельцами {sorted(declared_by)}")
        if name not in metadata.tables:
            problems.append(f"{name}: объявлена {declared_by[0]}, но такой таблицы нет")
    return sorted(problems)


def holds_person(table: Table) -> bool:
    """Whether the table keeps rows of a person: their id or a foreign key to the account."""
    return PERSON_COLUMN in table.columns or any(
        key.target_fullname.split(".")[0] == ACCOUNTS_TABLE for key in table.foreign_keys
    )


def core_account_data_bindings(transactions: HomeTransactions) -> tuple[PortBinding[Any], ...]:
    """Core's own erasure handler, bound beside the slices' ones."""
    return (ACCOUNT_DATA_HANDLERS.bind(CoreAccountData(transactions)),)


def check_account_handlers(specs: Sequence[AccountDataSpec], ports: PortDirectory) -> None:
    """Refuse to start when an owner that erases data has no handler, or two."""
    problems = handler_problems(specs, ports.all(ACCOUNT_DATA_HANDLERS))
    if problems:
        message = "реестр стирания: " + "; ".join(problems)
        raise RuntimeError(message)
