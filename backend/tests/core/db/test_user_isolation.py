"""Person isolation: the second line for tables that are personal by nature (ADR 0053 point 2)."""

import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
import sqlalchemy as sa
from alembic import op
from sqlalchemy import exc

from shosai.core.config.roles import ProcessRole
from shosai.core.db.migration_scope import (
    MigrationScope,
    disable_user_isolation,
    enable_user_isolation,
    grant_to_application,
    grant_to_sweeper,
    revoke_from_sweeper,
)
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from tests.core.db.operations import run_step_everywhere
from tests.harness.database_access import (
    DatabaseAccess,
    ProcessShape,
    open_database_access,
    slot_urls,
)
from tests.harness.run_slot import RunSlot

TABLE = "probe_personal_notes"
NOTES = sa.table(TABLE, sa.column("id", sa.Uuid()), sa.column("user_id", sa.Uuid()))


def create_table(scope: MigrationScope) -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
    )
    grant_to_application(scope, TABLE)
    grant_to_sweeper(TABLE, ("SELECT",))
    enable_user_isolation(TABLE)


def drop_table(_scope: MigrationScope) -> None:
    disable_user_isolation(TABLE)
    revoke_from_sweeper(TABLE)
    op.drop_table(TABLE)


@pytest_asyncio.fixture
async def personal_table(run_slot: RunSlot) -> AsyncIterator[None]:
    await run_step_everywhere(run_slot, create_table)
    try:
        yield
    finally:
        await run_step_everywhere(run_slot, drop_table)


async def owners(
    access: DatabaseAccess, scope: TenancyScope, *, sweep: bool = False
) -> set[uuid.UUID]:
    async with access.transactions.begin(scope, read_only=True, sweep=sweep) as session:
        return set((await session.execute(sa.select(NOTES.c.user_id))).scalars())


async def test_a_person_reads_and_writes_only_their_own_rows(
    homes: DatabaseAccess, personal_table: None, run_slot: RunSlot
) -> None:
    anna, boris = uuid.uuid4(), uuid.uuid4()
    for person in (anna, boris):
        async with homes.transactions.begin(TenancyScope(Home.RU, person)) as session:
            await session.execute(sa.insert(NOTES).values(id=uuid.uuid4(), user_id=person))

    assert await owners(homes, TenancyScope(Home.RU, anna)) == {anna}
    assert await owners(homes, TenancyScope(Home.RU)) == set()
    async with open_database_access(
        slot_urls(run_slot), ProcessShape(role=ProcessRole.WORKERS)
    ) as workers:
        await workers.gate.verify_at_start()
        assert await owners(workers, TenancyScope(Home.RU), sweep=True) == {anna, boris}


async def test_a_row_of_another_person_cannot_be_written(
    homes: DatabaseAccess, personal_table: None
) -> None:
    with pytest.raises(exc.ProgrammingError, match="row-level security"):
        async with homes.transactions.begin(TenancyScope(Home.EU, uuid.uuid4())) as session:
            await session.execute(sa.insert(NOTES).values(id=uuid.uuid4(), user_id=uuid.uuid4()))
