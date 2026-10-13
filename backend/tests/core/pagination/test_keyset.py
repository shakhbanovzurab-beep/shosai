"""Keyset pages: rows inserted between pages neither repeat nor shift the next page (§10)."""

import uuid
from collections.abc import Sequence
from typing import Any

import pytest
import sqlalchemy as sa
from pydantic import BaseModel

from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.pagination.cursor import CursorCodec
from shosai.core.pagination.keyset import Keyset
from shosai.core.pagination.page import Page, PageRequest, page_of
from tests.core.db.probe_table import probe_records
from tests.harness.database_access import DatabaseAccess


class Position(BaseModel):
    """The id a page of probe rows ended at."""

    id: uuid.UUID


CODEC = CursorCodec("probe.records", Position)


async def insert(homes: DatabaseAccess, ids: Sequence[uuid.UUID]) -> None:
    """Probe rows with the given ids."""
    async with homes.transactions.begin(TenancyScope(Home.RU)) as session:
        await session.execute(sa.insert(probe_records), [{"id": id_, "note": "n"} for id_ in ids])


async def read_page(homes: DatabaseAccess, keyset: Keyset, request: PageRequest) -> Page[uuid.UUID]:
    """One page of probe ids after the request's cursor."""
    after: Sequence[Any] | None = None
    if request.cursor is not None:
        after = (CODEC.decode(request.cursor).id,)
    statement = keyset.page(sa.select(probe_records.c.id), after, request.limit)
    async with homes.transactions.begin(TenancyScope(Home.RU), read_only=True) as session:
        rows = (await session.execute(statement)).all()
    return page_of(rows, request, CODEC, lambda row: row.id, lambda row: Position(id=row.id))


async def test_a_cursor_survives_inserts_between_pages(
    homes: DatabaseAccess, probe_table: sa.TableClause
) -> None:
    keyset = Keyset((probe_records.c.id,))
    ids = [uuid.uuid7() for _ in range(5)]
    await insert(homes, ids)

    first = await read_page(homes, keyset, PageRequest(limit=2))
    earlier, later = uuid.UUID(int=1), uuid.uuid7()
    await insert(homes, [earlier, later])
    second = await read_page(homes, keyset, PageRequest(limit=2, cursor=first.next_cursor))
    third = await read_page(homes, keyset, PageRequest(limit=2, cursor=second.next_cursor))

    assert first.items == ids[:2]
    assert second.items == ids[2:4]
    assert third.items == [ids[4], later]
    assert third.next_cursor is None


async def test_a_descending_key_pages_from_the_newest(
    homes: DatabaseAccess, probe_table: sa.TableClause
) -> None:
    keyset = Keyset((probe_records.c.id,), descending=True)
    ids = [uuid.uuid7() for _ in range(3)]
    await insert(homes, ids)

    first = await read_page(homes, keyset, PageRequest(limit=2))
    second = await read_page(homes, keyset, PageRequest(limit=2, cursor=first.next_cursor))

    assert first.items == ids[:0:-1]
    assert second.items == ids[:1]
    assert second.next_cursor is None


def test_a_position_must_match_the_sort_key() -> None:
    keyset = Keyset((probe_records.c.id,))

    with pytest.raises(ValueError, match="позиция"):
        keyset.page(sa.select(probe_records.c.id), (1, 2), 10)
    with pytest.raises(ValueError, match="ключ сортировки"):
        Keyset(())
