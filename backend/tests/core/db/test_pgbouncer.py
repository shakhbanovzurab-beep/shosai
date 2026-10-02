"""Transactions behind PgBouncer in transaction mode (ADR 0001, ADR 0013).

The scope set by one transaction never reaches the next client of the same server
connection; a scoped read costs four round trips; concurrent transactions of several
processes share the server connections without seeing each other's scope.
"""

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import timedelta

import pytest
import pytest_asyncio
import sqlalchemy as sa

from tests.core.db.tcp_proxy import CountingProxy, Upstream, through
from tests.harness.database_access import (
    DatabaseAccess,
    ProcessShape,
    open_database_access,
    slot_urls,
)
from tests.harness.run_slot import RunSlot
from whisperer.core.config.roles import ProcessRole
from whisperer.core.db.engines import DatabaseProfile
from whisperer.core.kernel.homes import Home
from whisperer.core.kernel.tenancy import TenancyScope

SINGLE_CONNECTION = DatabaseProfile(pool_size=1, statement_timeout=timedelta(seconds=10))
SERVER_AND_SCOPE = sa.text(
    "SELECT pg_backend_pid() AS pid, current_setting('app.user_id', true) AS user_id, "
    "current_setting('statement_timeout') AS statement_timeout"
)
SAME_SERVER_ATTEMPTS = 20
CONCURRENT_PROCESSES = 3
TRANSACTIONS_PER_PROCESS = 60


@pytest_asyncio.fixture
async def counted_ru(run_slot: RunSlot) -> AsyncIterator[tuple[CountingProxy, DatabaseAccess]]:
    """Database access whose RU engine goes through a counting proxy to the RU PgBouncer."""
    urls = slot_urls(run_slot)
    target = run_slot.claimed.targets(Home.RU).application
    proxy = CountingProxy(Upstream(target.host, target.port))
    port = await proxy.start()
    try:
        urls[Home.RU] = through(urls[Home.RU], port)
        async with open_database_access(urls, ProcessShape(profile=SINGLE_CONNECTION)) as access:
            await access.gate.verify_at_start()
            yield proxy, access
    finally:
        await proxy.stop()


async def test_the_scope_does_not_reach_the_next_transaction_on_the_server(
    run_slot: RunSlot,
) -> None:
    async with open_database_access(
        slot_urls(run_slot), ProcessShape(profile=SINGLE_CONNECTION)
    ) as access:
        await access.gate.verify_at_start()
        engine = access.databases.engine(Home.RU)
        same_server_seen = 0
        for _ in range(SAME_SERVER_ATTEMPTS):
            scope = TenancyScope(Home.RU, user_id=uuid.uuid4())
            async with access.transactions.begin(scope) as session:
                scoped = (await session.execute(SERVER_AND_SCOPE)).one()
            # Следующий клиент того же серверного соединения — без области HomeTransactions.
            async with engine.connect() as connection:
                after = (await connection.execute(SERVER_AND_SCOPE)).one()
            assert scoped.user_id == str(scope.user_id)
            if after.pid == scoped.pid:
                same_server_seen += 1
                assert after.user_id in {None, ""}
                assert after.statement_timeout == "0"

    assert same_server_seen > 0, "PgBouncer ни разу не вернул то же серверное соединение"


async def test_a_scoped_read_costs_four_round_trips(
    counted_ru: tuple[CountingProxy, DatabaseAccess],
) -> None:
    proxy, access = counted_ru
    scope = TenancyScope(Home.RU, user_id=uuid.uuid4())

    proxy.reset()
    async with access.transactions.begin(scope, read_only=True) as session:
        await session.execute(sa.text("SELECT 1"))
    one_statement = proxy.turns

    proxy.reset()
    async with access.transactions.begin(scope) as session:
        for _ in range(3):
            await session.execute(sa.text("SELECT 1"))
    three_statements = proxy.turns

    # BEGIN, область, выражения по одному обмену, COMMIT.
    assert (one_statement, three_statements) == (4, 6)


async def test_concurrent_processes_never_see_each_other_s_scope(run_slot: RunSlot) -> None:
    async def process() -> None:
        async with open_database_access(
            slot_urls(run_slot), ProcessShape(role=ProcessRole.WORKERS)
        ) as access:
            await access.gate.verify_at_start()
            await asyncio.gather(
                *(
                    scoped_read(access, home)
                    for home in list(Home) * (TRANSACTIONS_PER_PROCESS // 2)
                )
            )

    await asyncio.gather(*(process() for _ in range(CONCURRENT_PROCESSES)))


async def scoped_read(access: DatabaseAccess, home: Home) -> None:
    """A transaction that must see exactly its own scope and its own home."""
    scope = TenancyScope(home, user_id=uuid.uuid4(), org_id=uuid.uuid4())
    async with access.transactions.begin(scope, read_only=True) as session:
        row = (
            await session.execute(
                sa.text(
                    "SELECT app_user_id() AS user_id, app_org_id() AS org_id, "
                    "(SELECT home FROM home_identity) AS home, pg_sleep(0.01)"
                )
            )
        ).one()
    assert (row.user_id, row.org_id, row.home) == (scope.user_id, scope.org_id, home.value)


@pytest.mark.parametrize("home", list(Home))
async def test_no_prepared_statement_is_left_on_the_server(
    homes: DatabaseAccess, home: Home
) -> None:
    async with homes.transactions.begin(TenancyScope(home), read_only=True) as session:
        await session.execute(sa.text("SELECT 1"))
        prepared = (
            await session.execute(sa.text("SELECT count(*) FROM pg_prepared_statements"))
        ).scalar()

    assert prepared == 0
