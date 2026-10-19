"""A person's rows of one table, page by page: as JSON Lines for export, or copied to a home.

Each page is read in its own short transaction, ordered by a unique key, so no transaction
stays open while the archive goes to storage or across both homes (§14 rule 1), and a
table of any size never sits whole in memory. A table may narrow a person's rows (`only`),
to those that move with them. Export takes only the listed columns:
hashes, secrets and ciphertexts are never listed. A copy takes whole rows and inserts
them in the other home, skipping the ones already there, so a repeat adds nothing.
"""

import hashlib
import json
from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Final
from uuid import UUID

from sqlalchemy import ColumnElement, Table, exists, select
from sqlalchemy.dialects.postgresql import insert

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope

PAGE_ROWS: Final = 1000
PERSON_COLUMN: Final = "user_id"


@dataclass(frozen=True, slots=True)
class PersonRows:
    """What of a table goes into the archive: the columns and the unique key to page by."""

    table: Table
    columns: tuple[str, ...]
    key: str
    # Колонка с идентификатором человека; у таблицы аккаунтов это её ключ.
    person: str = PERSON_COLUMN
    # Сужение строк человека, например до тех, что переезжают с ним; None — все его строки.
    only: Callable[[UUID], ColumnElement[bool]] | None = None

    def __post_init__(self) -> None:
        unknown = {*self.columns, self.key, self.person} - set(self.table.columns.keys())
        if unknown:
            message = f"выгрузка {self.table.name}: нет колонок {sorted(unknown)}"
            raise ValueError(message)


def person_filter(rows: PersonRows, user_id: UUID) -> list[ColumnElement[bool]]:
    """The conditions that pick the person's rows of the table, narrowed when `only` says."""
    conditions = [rows.table.c[rows.person] == user_id]
    if rows.only is not None:
        conditions.append(rows.only(user_id))
    return conditions


async def person_lines(
    transactions: HomeTransactions, scope: TenancyScope, rows: PersonRows, user_id: UUID
) -> AsyncIterator[bytes]:
    """The person's rows of the table, one JSON object per line, a page per chunk."""
    table, key = rows.table, rows.table.c[rows.key]
    last: object = None
    while True:
        query = select(*(table.c[name] for name in rows.columns), key.label("_page_key"))
        query = query.where(*person_filter(rows, user_id))
        if last is not None:
            query = query.where(key > last)
        async with transactions.begin(scope, read_only=True) as session:
            page = (await session.execute(query.order_by(key).limit(PAGE_ROWS))).mappings().all()
        if not page:
            return
        yield json_lines([{name: row[name] for name in rows.columns} for row in page])
        if len(page) < PAGE_ROWS:
            return
        last = page[-1]["_page_key"]


async def tables_holding(
    transactions: HomeTransactions, scope: TenancyScope, tables: Sequence[Table], user_id: UUID
) -> tuple[str, ...]:
    """The tables that still hold a row of the person in the scope's home, in one round trip."""
    checks = [
        exists().where(table.c[PERSON_COLUMN] == user_id).label(table.name) for table in tables
    ]
    async with transactions.begin(scope, read_only=True) as session:
        found = (await session.execute(select(*checks))).one()
    return tuple(table.name for table, holds in zip(tables, found, strict=True) if holds)


def whole_rows(table: Table, key: str, person: str = PERSON_COLUMN) -> PersonRows:
    """Every column of the table: what a copy between homes moves."""
    return PersonRows(table, tuple(table.columns.keys()), key=key, person=person)


async def copy_person_rows(
    transactions: HomeTransactions, rows: PersonRows, user_id: UUID, homes: tuple[Home, Home]
) -> int:
    """Copy the person's rows from the first home to the second; how many were read."""
    source, target = homes
    table, key = rows.table, rows.table.c[rows.key]
    last: object = None
    copied = 0
    while True:
        query = select(*(table.c[name] for name in rows.columns), key.label("_page_key"))
        query = query.where(*person_filter(rows, user_id))
        if last is not None:
            query = query.where(key > last)
        async with transactions.begin(TenancyScope(source, user_id), read_only=True) as session:
            page = (await session.execute(query.order_by(key).limit(PAGE_ROWS))).mappings().all()
        if not page:
            return copied
        values = [{name: row[name] for name in rows.columns} for row in page]
        async with transactions.begin(TenancyScope(target, user_id)) as session:
            await session.execute(insert(table).values(values).on_conflict_do_nothing())
        copied += len(page)
        if len(page) < PAGE_ROWS:
            return copied
        last = page[-1]["_page_key"]


async def person_digest(
    transactions: HomeTransactions, scope: TenancyScope, rows: PersonRows, user_id: UUID
) -> str:
    """The SHA-256 of the person's rows of the table in the scope's home, in key order."""
    digest = hashlib.sha256()
    async for chunk in person_lines(transactions, scope, rows, user_id):
        digest.update(chunk)
    return digest.hexdigest()


def json_lines(records: Sequence[Mapping[str, Any]]) -> bytes:
    """Records as UTF-8 JSON Lines; times in ISO 8601, ids and addresses as text."""
    return "".join(
        json.dumps(record, ensure_ascii=False, default=_plain, sort_keys=True) + "\n"
        for record in records
    ).encode()


def _plain(value: object) -> str:
    if isinstance(value, datetime | date):
        return value.isoformat()
    return str(value)
