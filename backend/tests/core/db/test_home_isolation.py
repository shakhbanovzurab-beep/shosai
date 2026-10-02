"""A transaction sees only the data of its own home (target architecture §4.1, inv-15)."""

import uuid

import pytest
import sqlalchemy as sa

from tests.harness.connections import fetch_value
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot
from whisperer.core.kernel.homes import Home
from whisperer.core.kernel.tenancy import TenancyScope

OTHER_HOME = {Home.RU: Home.EU, Home.EU: Home.RU}


@pytest.mark.parametrize("home", list(Home))
async def test_a_row_written_in_one_home_is_invisible_from_the_other(
    homes: DatabaseAccess, probe_table: sa.TableClause, run_slot: RunSlot, home: Home
) -> None:
    record_id = uuid.uuid4()
    async with homes.transactions.begin(TenancyScope(home)) as session:
        await session.execute(
            sa.insert(probe_table).values(id=record_id, org_id=None, note=home.value)
        )

    seen = {}
    for reader in Home:
        async with homes.transactions.begin(TenancyScope(reader), read_only=True) as session:
            seen[reader] = (
                await session.execute(
                    sa.select(probe_table.c.note).where(probe_table.c.id == record_id)
                )
            ).scalar_one_or_none()

    assert seen == {home: home.value, OTHER_HOME[home]: None}
    stored_in = {
        server: await fetch_value(
            connection, "SELECT count(*) FROM probe_records WHERE id = %s", (record_id,)
        )
        for server, connection in run_slot.claimed.connections.items()
    }
    assert stored_in == {home: 1, OTHER_HOME[home]: 0}


@pytest.mark.parametrize("home", list(Home))
async def test_each_engine_reaches_the_database_of_its_home(
    homes: DatabaseAccess, home: Home
) -> None:
    async with homes.transactions.begin(TenancyScope(home), read_only=True) as session:
        found = (await session.execute(sa.text("SELECT home FROM home_identity"))).scalar_one()

    assert found == home.value
