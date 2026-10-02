"""Transactions in the home of a scope: scope settings, read-only mode, commit and rollback."""

import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy import exc

from tests.harness.database_access import (
    DatabaseAccess,
    ProcessShape,
    open_database_access,
    slot_urls,
)
from tests.harness.run_slot import RunSlot
from whisperer.core.config.roles import ProcessRole
from whisperer.core.kernel.homes import Home
from whisperer.core.kernel.tenancy import TenancyScope

SCOPE_SETTINGS = sa.text(
    "SELECT current_setting('statement_timeout') AS statement_timeout, "
    "current_setting('transaction_read_only') AS read_only, "
    "app_user_id() AS user_id, app_org_id() AS org_id"
)


class ProbeError(Exception):
    """An error the block of a transaction raises on purpose."""


@pytest.mark.parametrize("home", list(Home))
async def test_the_first_statement_sets_the_scope_of_the_transaction(
    homes: DatabaseAccess, home: Home
) -> None:
    scope = TenancyScope(home, user_id=uuid.uuid4(), org_id=uuid.uuid4())

    async with homes.transactions.begin(scope) as session:
        row = (await session.execute(SCOPE_SETTINGS)).one()

    assert row.statement_timeout == "10s"
    assert row.read_only == "off"
    assert (row.user_id, row.org_id) == (scope.user_id, scope.org_id)


async def test_a_scope_without_account_and_company_reads_as_null(homes: DatabaseAccess) -> None:
    async with homes.transactions.begin(TenancyScope(Home.EU)) as session:
        row = (await session.execute(SCOPE_SETTINGS)).one()

    assert (row.user_id, row.org_id) == (None, None)


async def write_in_read_only(access: DatabaseAccess) -> None:
    """Try to create a temporary table in a read-only transaction."""
    async with access.transactions.begin(TenancyScope(Home.RU), read_only=True) as session:
        assert (await session.execute(SCOPE_SETTINGS)).one().read_only == "on"
        await session.execute(sa.text("CREATE TEMPORARY TABLE probe_write (id integer)"))


async def insert_then_fail(access: DatabaseAccess, table: sa.TableClause) -> None:
    """Insert a row, then fail inside the same transaction."""
    record = {"id": uuid.uuid4(), "org_id": None, "note": "rolled back"}
    async with access.transactions.begin(TenancyScope(Home.EU)) as session:
        await session.execute(sa.insert(table).values(record))
        raise ProbeError


async def test_a_read_only_transaction_refuses_to_write(homes: DatabaseAccess) -> None:
    with pytest.raises(exc.InternalError, match="read-only transaction"):
        await write_in_read_only(homes)


async def test_the_block_commits_on_exit(
    homes: DatabaseAccess, probe_table: sa.TableClause
) -> None:
    record = {"id": uuid.uuid4(), "org_id": None, "note": "committed"}
    async with homes.transactions.begin(TenancyScope(Home.RU)) as session:
        await session.execute(sa.insert(probe_table).values(record))

    async with homes.transactions.begin(TenancyScope(Home.RU), read_only=True) as session:
        notes = (await session.execute(sa.select(probe_table.c.note))).scalars().all()

    assert notes == ["committed"]


async def test_an_error_in_the_block_rolls_back(
    homes: DatabaseAccess, probe_table: sa.TableClause
) -> None:
    with pytest.raises(ProbeError):
        await insert_then_fail(homes, probe_table)

    async with homes.transactions.begin(TenancyScope(Home.EU), read_only=True) as session:
        count = (
            await session.execute(sa.select(sa.func.count()).select_from(probe_table))
        ).scalar()

    assert count == 0


async def test_workers_get_their_longer_statement_timeout(run_slot: RunSlot) -> None:
    async with open_database_access(
        slot_urls(run_slot), ProcessShape(role=ProcessRole.WORKERS)
    ) as access:
        await access.gate.verify_at_start()
        async with access.transactions.begin(TenancyScope(Home.RU)) as session:
            row = (await session.execute(SCOPE_SETTINGS)).one()

    assert row.statement_timeout == "1min"
