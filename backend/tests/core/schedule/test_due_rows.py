"""A due-row sweep claims each due row once under concurrency, for a lease (§12, F6-C14)."""

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import timedelta

import pytest
import pytest_asyncio
import sqlalchemy as sa
from alembic import op
from psycopg import sql

from shosai.core.db.migration_scope import MigrationScope, grant_to_application
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.schedule.due_rows import DueRows, claim_due
from tests.core.db.operations import run_step
from tests.harness.connections import Connection
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot

TABLE = "probe_errands"
errands = sa.table(
    TABLE,
    sa.column("id", sa.Uuid()),
    sa.column("run_at", sa.DateTime(timezone=True)),
    sa.column("status", sa.Text()),
)
DUE = DueRows(errands, errands.c.id, errands.c.run_at, errands.c.status == "pending")


def create_errands(scope: MigrationScope) -> None:
    """A slice's table of rows that fall due."""
    op.create_table(
        TABLE,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
    )
    grant_to_application(scope, TABLE)


def drop_errands(_scope: MigrationScope) -> None:
    """Undo `create_errands`."""
    op.drop_table(TABLE)


@pytest_asyncio.fixture
async def errands_table(run_slot: RunSlot) -> AsyncIterator[Connection]:
    """`probe_errands` in the RU home for one test: 100 due, 10 later, 10 done."""
    await run_step(run_slot, Home.RU, create_errands)
    connection = run_slot.claimed.connections[Home.RU]
    try:
        for count, offset, status in ((100, "-1 minute", "pending"), (10, "1 hour", "pending"),
                                      (10, "-1 hour", "done")):  # fmt: skip
            await connection.execute(
                sql.SQL(
                    "INSERT INTO {} SELECT gen_random_uuid(), now() + %s::interval, %s "
                    "FROM generate_series(1, %s)"
                ).format(sql.Identifier(TABLE)),
                (offset, status, count),
            )
        yield connection
    finally:
        await run_step(run_slot, Home.RU, drop_errands)


async def sweep(homes: DatabaseAccess, lease: timedelta, limit: int = 30) -> list[uuid.UUID]:
    """One sweep: claim up to `limit` rows and hold the transaction a moment, as work would."""
    async with homes.transactions.begin(TenancyScope(Home.RU)) as session:
        rows = await claim_due(session, DUE, limit=limit, lease=lease)
        await asyncio.sleep(0.05)
    return [row.id for row in rows]


async def test_concurrent_sweeps_claim_each_due_row_once(
    homes: DatabaseAccess, errands_table: Connection
) -> None:
    claimed = await asyncio.gather(*(sweep(homes, timedelta(minutes=5)) for _ in range(5)))
    rest = await sweep(homes, timedelta(minutes=5))

    every = [row for batch in claimed for row in batch]
    assert len(every) == len(set(every)) == 100
    assert rest == []


async def test_a_claim_whose_sweep_died_comes_due_again_after_its_lease(
    homes: DatabaseAccess, errands_table: Connection
) -> None:
    first = await sweep(homes, timedelta(milliseconds=200))
    await errands_table.execute("SELECT pg_sleep(0.25)")
    # Истёкшие захваты получили срок позже нетронутых строк: обход старшие берёт первыми.
    second = await sweep(homes, timedelta(minutes=5), limit=200)

    assert len(first) == 30
    assert len(second) == 100
    assert set(first) <= set(second)


@pytest.mark.parametrize(("limit", "lease"), [(0, timedelta(seconds=1)), (10, timedelta(0))])
async def test_a_claim_needs_a_limit_and_a_lease(
    homes: DatabaseAccess, limit: int, lease: timedelta
) -> None:
    with pytest.raises(ValueError, match="захват строк"):
        async with homes.transactions.begin(TenancyScope(Home.RU)) as session:
            await claim_due(session, DUE, limit=limit, lease=lease)
