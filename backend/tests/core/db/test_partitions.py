"""Monthly partitions: created ahead by a tick, dropped after their retention (§8.2, A8).

A probe table partitioned by month lives in both homes for one test. The tick runs as the
application role, the way the workers run it; the schema steps run as the migration role.
"""

import uuid
from collections.abc import AsyncIterator
from datetime import timedelta

import psycopg
import pytest
import pytest_asyncio
import sqlalchemy as sa
from alembic import op
from prometheus_client import CollectorRegistry
from psycopg import sql
from sqlalchemy.exc import DBAPIError

from shosai.core.db.migration_scope import MigrationScope, grant_to_application
from shosai.core.db.partitions.policy import (
    MonthlyPartitions,
    is_model_table,
    monthly_partition_range,
    policies,
    register_monthly_partitions,
    unregister_monthly_partitions,
)
from shosai.core.db.partitions.upkeep import PartitionMetrics, PartitionUpkeep
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from tests.core.db.operations import run_step, run_step_everywhere
from tests.harness.catalog import CatalogFingerprint
from tests.harness.connections import Connection, connect, fetch_rows, fetch_value
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot

TABLE = "probe_events"
OLD_PARTITION = f"{TABLE}_p202001"
events = sa.table(
    TABLE, sa.column("id", sa.Uuid()), sa.column("occurred_at", sa.DateTime(timezone=True))
)


def create_events(scope: MigrationScope) -> None:
    """A parent partitioned by month whose policy is registered without its partitions."""
    op.create_table(
        TABLE,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", "occurred_at"),
        postgresql_partition_by=monthly_partition_range("occurred_at"),
    )
    grant_to_application(scope, TABLE)
    op.execute(sa.insert(policies).values(table_name=TABLE, ahead_months=2, keep_months=2))


def drop_events(_scope: MigrationScope) -> None:
    """Undo `create_events`: the parent goes with its partitions."""
    unregister_monthly_partitions(TABLE)
    op.drop_table(TABLE)


def attach_old_partition(_scope: MigrationScope) -> None:
    """A partition of January 2020, long past any retention."""
    op.execute(
        f"CREATE TABLE {OLD_PARTITION} PARTITION OF {TABLE} "
        "FOR VALUES FROM ('2020-01-01 00:00+00') TO ('2020-02-01 00:00+00')"
    )


@pytest_asyncio.fixture
async def events_table(run_slot: RunSlot) -> AsyncIterator[str]:
    """`probe_events` in both homes for one test; dropped after it."""
    await run_step_everywhere(run_slot, create_events)
    try:
        yield TABLE
    finally:
        await run_step_everywhere(run_slot, drop_events)


async def partitions(connection: Connection, table: str = TABLE) -> list[str]:
    """The partitions of the table, by name."""
    rows = await fetch_rows(
        connection,
        "SELECT child.relname FROM pg_inherits JOIN pg_class AS child "
        "ON child.oid = pg_inherits.inhrelid WHERE inhparent = %s::regclass ORDER BY 1",
        (table,),
    )
    return [row["relname"] for row in rows]


async def months_from_now(connection: Connection, *offsets: int) -> list[str]:
    """Partition names of this month (0) and its neighbours, by the database's clock in UTC."""
    names = []
    for offset in offsets:
        month = await fetch_value(
            connection,
            "SELECT to_char(date_trunc('month', now() AT TIME ZONE 'UTC') "
            "+ make_interval(months => %s), 'YYYYMM')",
            (offset,),
        )
        names.append(f"{TABLE}_p{month}")
    return names


def upkeep(homes: DatabaseAccess) -> tuple[PartitionUpkeep, CollectorRegistry]:
    """The upkeep as a worker runs it, with its own metrics."""
    registry = CollectorRegistry()
    return PartitionUpkeep(homes.transactions, PartitionMetrics(registry)), registry


@pytest.mark.parametrize("home", list(Home))
async def test_a_tick_creates_this_month_and_the_next_two(
    homes: DatabaseAccess, events_table: str, run_slot: RunSlot, home: Home
) -> None:
    connection = run_slot.claimed.connections[home]
    runner, registry = upkeep(homes)

    [first] = await runner.maintain(home)
    [second] = await runner.maintain(home)

    expected = await months_from_now(connection, 0, 1, 2)
    assert await partitions(connection) == expected
    assert (first.table, list(first.created)) == (events_table, expected)
    assert second.created == ()
    labels = {"home": home.value, "table": TABLE}
    assert registry.get_sample_value("shosai_partitions_created_total", labels) == 3
    coverage = registry.get_sample_value("shosai_partition_coverage_seconds", labels) or 0
    assert coverage > timedelta(days=59).total_seconds()


async def test_an_expired_partition_is_dropped_with_its_rows_and_recent_ones_stay(
    homes: DatabaseAccess, events_table: str, run_slot: RunSlot
) -> None:
    await run_step(run_slot, Home.EU, attach_old_partition)
    async with homes.transactions.begin(TenancyScope(Home.EU)) as session:
        await session.execute(
            sa.insert(events).values(id=uuid.uuid7(), occurred_at=sa.text("'2020-01-15+00'"))
        )
    runner, _ = upkeep(homes)

    [result] = await runner.maintain(Home.EU)

    connection = run_slot.claimed.connections[Home.EU]
    assert result.dropped == (OLD_PARTITION,)
    assert OLD_PARTITION not in await partitions(connection)
    count = sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(TABLE))
    assert await fetch_value(connection, count) == 0


async def test_a_partition_a_reader_holds_is_deferred_not_waited_for(
    homes: DatabaseAccess, events_table: str, run_slot: RunSlot
) -> None:
    await run_step(run_slot, Home.RU, attach_old_partition)
    reader = await connect(run_slot.claimed.targets(Home.RU).migration)
    runner, _ = upkeep(homes)
    try:
        async with reader.transaction():
            await reader.execute(f"LOCK TABLE {TABLE} IN ACCESS SHARE MODE")
            [held] = await runner.maintain(Home.RU)
    finally:
        await reader.close()
    [freed] = await runner.maintain(Home.RU)

    assert (held.deferred, held.dropped, len(held.created)) == ((OLD_PARTITION,), (), 3)
    assert freed.dropped == (OLD_PARTITION,)


async def test_the_application_can_neither_change_a_policy_nor_drop_a_partition(
    homes: DatabaseAccess, events_table: str
) -> None:
    runner, _ = upkeep(homes)
    [result] = await runner.maintain(Home.RU)
    forbidden: list[sa.Executable] = [
        sa.text(f"DROP TABLE {result.created[0]}"),
        sa.update(policies).values(keep_months=1),
        sa.text("SELECT * FROM maintain_monthly_partitions('outbox_messages')"),
    ]

    for statement in forbidden:
        with pytest.raises(DBAPIError) as raised:
            async with homes.transactions.begin(TenancyScope(Home.RU)) as session:
                await session.execute(statement)
        assert isinstance(raised.value.orig, psycopg.Error)


async def test_registering_a_table_creates_its_partitions_at_once(run_slot: RunSlot) -> None:
    ledger = MonthlyPartitions("probe_ledger", ahead_months=1)

    def create(scope: MigrationScope) -> None:
        op.create_table(
            ledger.table,
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id", "recorded_at"),
            postgresql_partition_by=monthly_partition_range("recorded_at"),
        )
        register_monthly_partitions(ledger)

    def drop(_scope: MigrationScope) -> None:
        unregister_monthly_partitions(ledger.table)
        op.drop_table(ledger.table)

    connection = run_slot.claimed.connections[Home.RU]
    before = await CatalogFingerprint.take(connection)
    await run_step(run_slot, Home.RU, create)
    try:
        created = await partitions(connection, ledger.table)
        keep = await fetch_value(
            connection,
            "SELECT keep_months FROM partition_policies WHERE table_name = %s",
            (ledger.table,),
        )
    finally:
        await run_step(run_slot, Home.RU, drop)
    after = await CatalogFingerprint.take(connection)

    assert len(created) == 2
    assert keep is None
    assert after.changes_since(before) == []


async def test_a_downgrade_after_upkeep_restores_the_catalog(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    connection = run_slot.claimed.connections[Home.EU]
    before = await CatalogFingerprint.take(connection)
    await run_step_everywhere(run_slot, create_events)
    try:
        await run_step(run_slot, Home.EU, attach_old_partition)
        runner, _ = upkeep(homes)
        await runner.maintain(Home.EU)
    finally:
        await run_step_everywhere(run_slot, drop_events)

    assert (await CatalogFingerprint.take(connection)).changes_since(before) == []


@pytest.mark.parametrize(
    ("table", "ahead", "keep", "problem"),
    [
        ("Events", 2, None, "snake_case"),
        ("events", 0, None, "вперёд"),
        ("events", 13, None, "вперёд"),
        ("events", 2, 0, "хранятся"),
    ],
)
def test_a_policy_is_bounded(table: str, ahead: int, keep: int | None, problem: str) -> None:
    with pytest.raises(ValueError, match=problem):
        MonthlyPartitions(table, ahead_months=ahead, keep_months=keep)


def test_schema_comparison_skips_monthly_partitions_only() -> None:
    assert not is_model_table("provider_costs_p202610", "table", {})
    assert is_model_table("provider_costs", "table", {})
    assert is_model_table("ix_provider_costs_p202610", "index", {})
