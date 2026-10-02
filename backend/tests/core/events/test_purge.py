"""Published events go after 7 days, delivery marks after 14, unpublished events never (F1-C5)."""

import uuid
from datetime import timedelta

import pytest
from prometheus_client import CollectorRegistry
from redis.asyncio import Redis

from tests.core.events.bench import event_bench, insert_raw_event
from tests.harness.connections import Connection, fetch_rows, fetch_value
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot
from whisperer.core.events.metrics import EventMetrics
from whisperer.core.events.purge import OutboxPurge, PurgeResult, Retention
from whisperer.core.events.system import PURGE_OUTBOX, event_task_handlers
from whisperer.core.kernel.homes import Home
from whisperer.core.tasks.payloads import HomeTaskPayload

DAY = timedelta(days=1)


async def published_event(connection: Connection, published_ago: timedelta) -> uuid.UUID:
    """An outbox row published `published_ago` before now."""
    event_id = await insert_raw_event(connection, "probe.note.written", age=published_ago)
    await connection.execute(
        "UPDATE outbox_messages SET published_at = now() - %s WHERE id = %s",
        (published_ago, event_id),
    )
    return event_id


async def delivery_mark(connection: Connection, processed_ago: timedelta) -> uuid.UUID:
    """A delivery mark written `processed_ago` before now."""
    event_id = uuid.uuid7()
    await connection.execute(
        "INSERT INTO processed_events (consumer, event_id, processed_at) "
        "VALUES ('mail.welcome', %s, now() - %s)",
        (event_id, processed_ago),
    )
    return event_id


@pytest.mark.parametrize("home", list(Home))
async def test_expired_rows_go_and_everything_else_stays(
    homes: DatabaseAccess, run_slot: RunSlot, home: Home
) -> None:
    connection = run_slot.claimed.connections[home]
    for _ in range(3):
        await published_event(connection, 8 * DAY)
    kept_published = await published_event(connection, 6 * DAY)
    never_published = await insert_raw_event(connection, "probe.note.written", age=30 * DAY)
    for _ in range(2):
        await delivery_mark(connection, 15 * DAY)
    kept_mark = await delivery_mark(connection, 13 * DAY)
    registry = CollectorRegistry()
    purge = OutboxPurge(homes.transactions, EventMetrics(registry), Retention(batch=2))

    result = await purge.purge(home)

    assert result == PurgeResult(published_events=3, delivery_marks=2)
    events = await fetch_rows(connection, "SELECT id FROM outbox_messages ORDER BY id")
    assert [row["id"] for row in events] == [kept_published, never_published]
    marks = await fetch_rows(connection, "SELECT event_id FROM processed_events")
    assert [row["event_id"] for row in marks] == [kept_mark]
    for table, count in (("outbox_messages", 3), ("processed_events", 2)):
        sample = registry.get_sample_value(
            "whisperer_outbox_purged_rows_total", {"home": home.value, "table": table}
        )
        assert sample == count


async def test_the_purge_tick_purges_the_home_its_payload_names(
    valkey: Redis, homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    connection = run_slot.claimed.connections[Home.EU]
    await published_event(connection, 8 * DAY)
    bench = event_bench(valkey, homes)
    [purge] = [
        handler
        for handler in event_task_handlers(bench.resources, bench.tasks.system.sender)
        if handler.task is PURGE_OUTBOX
    ]

    await purge.handle(HomeTaskPayload(home=Home.EU))

    assert await fetch_value(connection, "SELECT count(*) FROM outbox_messages") == 0


def test_marks_outlive_the_events_they_deduplicate() -> None:
    with pytest.raises(ValueError, match="дольше"):
        Retention(published_events=14 * DAY, delivery_marks=14 * DAY)
