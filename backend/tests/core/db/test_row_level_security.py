"""Row-level security as the second line of company isolation (target architecture §7).

The probe table carries the standard company policy of `enable_company_isolation`; the
application role meets it through PgBouncer, the migration role owns the table.
"""

import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy import exc

from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from tests.harness.connections import fetch_value
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot

COMPANY_A = uuid.UUID("0199a000-0000-7000-8000-00000000000a")
COMPANY_B = uuid.UUID("0199a000-0000-7000-8000-00000000000b")
ROWS = (("a", COMPANY_A), ("b", COMPANY_B), ("personal", None))


async def seed(run_slot: RunSlot, home: Home) -> None:
    """Rows of two companies and one personal row, written by the table's owner."""
    connection = run_slot.claimed.connections[home]
    for note, org_id in ROWS:
        await connection.execute(
            "INSERT INTO probe_records (id, org_id, note) VALUES (%s, %s, %s)",
            (uuid.uuid4(), org_id, note),
        )


async def visible_notes(
    access: DatabaseAccess, scope: TenancyScope, table: sa.TableClause
) -> set[str]:
    async with access.transactions.begin(scope, read_only=True) as session:
        return set((await session.execute(sa.select(table.c.note))).scalars())


@pytest.mark.parametrize("home", list(Home))
async def test_a_company_scope_sees_its_rows_and_personal_rows_only(
    homes: DatabaseAccess, probe_table: sa.TableClause, run_slot: RunSlot, home: Home
) -> None:
    await seed(run_slot, home)
    user = uuid.uuid4()

    seen_by_a = await visible_notes(homes, TenancyScope(home, user, COMPANY_A), probe_table)
    seen_by_b = await visible_notes(homes, TenancyScope(home, user, COMPANY_B), probe_table)
    seen_without_company = await visible_notes(homes, TenancyScope(home, user), probe_table)

    assert seen_by_a == {"a", "personal"}
    assert seen_by_b == {"b", "personal"}
    assert seen_without_company == {"personal"}


async def test_a_row_of_another_company_cannot_be_written(
    homes: DatabaseAccess, probe_table: sa.TableClause
) -> None:
    scope = TenancyScope(Home.RU, uuid.uuid4(), COMPANY_A)

    with pytest.raises(exc.ProgrammingError, match="row-level security"):
        async with homes.transactions.begin(scope) as session:
            await session.execute(
                sa.insert(probe_table).values(id=uuid.uuid4(), org_id=COMPANY_B, note="foreign")
            )


async def test_a_foreign_row_cannot_be_moved_into_view(
    homes: DatabaseAccess, probe_table: sa.TableClause, run_slot: RunSlot
) -> None:
    await seed(run_slot, Home.EU)
    scope = TenancyScope(Home.EU, uuid.uuid4(), COMPANY_A)

    async with homes.transactions.begin(scope) as session:
        moved = (
            await session.execute(
                sa.update(probe_table)
                .where(probe_table.c.note == "b")
                .values(org_id=COMPANY_A)
                .returning(probe_table.c.id)
            )
        ).all()

    assert moved == []
    owned_by_b = await fetch_value(
        run_slot.claimed.connections[Home.EU],
        "SELECT org_id FROM probe_records WHERE note = 'b'",
    )
    assert owned_by_b == COMPANY_B


async def test_the_migration_role_owns_the_table_and_sees_every_row(
    homes: DatabaseAccess, probe_table: sa.TableClause, run_slot: RunSlot
) -> None:
    await seed(run_slot, Home.RU)

    count = await fetch_value(
        run_slot.claimed.connections[Home.RU], "SELECT count(*) FROM probe_records"
    )

    assert count == len(ROWS)
