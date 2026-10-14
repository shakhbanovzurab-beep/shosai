"""Coverage of the export and deletion registry over the application's tables (§14 rule 7).

A table holds a person's rows when it has a `user_id` column or a foreign key to `users`.
Each such table is declared by exactly one owner (core or a slice) with its treatment,
and every declared table exists; a test runs this over the application metadata, so a
slice cannot add personal rows that deletion would miss (ADR 0045 point 7).
"""

from collections.abc import Sequence

from sqlalchemy import MetaData, Table

from shosai.core.account_data.spec import AccountDataSpec

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
