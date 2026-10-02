"""An event the relay cannot pass on waits and comes back; it is never dropped (§12, §16.4)."""

import pytest
from opentelemetry.sdk.trace import TracerProvider
from prometheus_client import CollectorRegistry
from redis.asyncio import Redis

from tests.core.events.bench import Applied, event_bench, insert_raw_event, outbox_rows, recording
from tests.core.events.relay_bench import RecordingSender, write_notes
from tests.core.kv.outages import closed_port, redis_url
from tests.core.observability.capture import captured_logs
from tests.core.tasks.workbench import workbench
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot
from whisperer.core.events.relay import OutboxRelay, RelayPass
from whisperer.core.events.system import event_task_handlers
from whisperer.core.kernel.homes import Home
from whisperer.core.kv.connection import connect_redis
from whisperer.core.tasks.errors import TaskQueueUnavailableError
from whisperer.core.tasks.queues import TaskQueue
from whisperer.core.tasks.system import build_task_system

# Пауза после сбоя отсчитывается от начала транзакции отметки: проверка допускает её длительность.
SETTLE_SLACK_SECONDS = 0.5


def outage() -> TaskQueueUnavailableError:
    """What the sender raises while Valkey is silent."""
    return TaskQueueUnavailableError(TaskQueue.DEFAULT)


async def test_an_outage_holds_back_the_event_and_releases_the_rest_of_the_pass(
    valkey: Redis, homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    bench = event_bench(valkey, homes, [recording("mail.welcome", Applied())])
    first, failed, untried = await write_notes(homes.transactions, bench.outbox, Home.EU, 3)
    connection = run_slot.claimed.connections[Home.EU]
    relay = OutboxRelay(bench.resources, RecordingSender(homes.databases, failures={2: outage()}))

    result = await relay.relay(Home.EU)
    rows = {row["id"]: row for row in await outbox_rows(connection)}
    retry = await OutboxRelay(bench.resources, RecordingSender(homes.databases)).relay(Home.EU)
    await connection.execute(
        "UPDATE outbox_messages SET available_at = now() WHERE id = %s", (failed,)
    )
    last = await OutboxRelay(bench.resources, RecordingSender(homes.databases)).relay(Home.EU)

    assert result == RelayPass(published=[first], held_back=[failed], released=[untried])
    assert (rows[first]["published"], rows[first]["attempts"]) == (True, 0)
    assert (rows[failed]["published"], rows[failed]["attempts"]) == (False, 1)
    assert 2 - SETTLE_SLACK_SECONDS < rows[failed]["due_in"] <= 2
    assert (rows[untried]["published"], rows[untried]["attempts"]) == (False, 0)
    assert rows[untried]["due_in"] <= 0
    assert retry == RelayPass(published=[untried])
    assert last == RelayPass(published=[failed])
    held_back = bench.sample(
        "whisperer_outbox_held_back_total", home="eu", reason="queue_unavailable"
    )
    assert held_back == 1


@pytest.mark.parametrize(
    ("attempts_before", "pause_seconds"),
    [(1, 4), (3, 16), (7, 256), (8, 300), (40, 300), (5000, 300)],
)
async def test_the_pause_doubles_with_each_failure_up_to_five_minutes(
    valkey: Redis,
    homes: DatabaseAccess,
    run_slot: RunSlot,
    attempts_before: int,
    pause_seconds: int,
) -> None:
    bench = event_bench(valkey, homes, [recording("mail.welcome", Applied())])
    await write_notes(homes.transactions, bench.outbox, Home.RU, 1)
    connection = run_slot.claimed.connections[Home.RU]
    await connection.execute("UPDATE outbox_messages SET attempts = %s", (attempts_before,))

    await OutboxRelay(
        bench.resources, RecordingSender(homes.databases, failures={1: outage()})
    ).relay(Home.RU)

    [row] = await outbox_rows(connection)
    assert row["attempts"] == attempts_before + 1
    assert pause_seconds - SETTLE_SLACK_SECONDS < row["due_in"] <= pause_seconds


async def test_a_silent_valkey_holds_events_back_through_the_real_sender(
    valkey: Redis, homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    bench = event_bench(valkey, homes, [recording("mail.welcome", Applied())])
    await write_notes(homes.transactions, bench.outbox, Home.RU, 2)
    stopped = connect_redis(redis_url(closed_port()), "whisperer-tests")
    try:
        tasks = build_task_system(
            stopped,
            lambda sender: event_task_handlers(bench.resources, sender),
            CollectorRegistry(),
            TracerProvider(),
        )
        result = await OutboxRelay(bench.resources, tasks.sender).relay(Home.RU)
    finally:
        await stopped.aclose()

    rows = await outbox_rows(run_slot.claimed.connections[Home.RU])
    assert (len(result.held_back), len(result.released), result.published) == (1, 1, [])
    assert [row["published"] for row in rows] == [False, False]
    assert sorted(row["attempts"] for row in rows) == [0, 1]


async def test_an_event_type_this_image_does_not_know_waits_for_one_that_does(
    valkey: Redis, homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    bench = event_bench(valkey, homes, [recording("mail.welcome", Applied())])
    connection = run_slot.claimed.connections[Home.RU]
    unknown = await insert_raw_event(connection, "billing.invoice.paid")
    [known] = await write_notes(homes.transactions, bench.outbox, Home.RU, 1)
    sender = RecordingSender(homes.databases)

    with captured_logs() as logs:
        result = await OutboxRelay(bench.resources, sender).relay(Home.RU)

    assert result == RelayPass(published=[known], held_back=[unknown])
    assert sender.event_ids() == [known]
    [line] = [line for line in logs.lines() if line["level"] == "error"]
    assert line["event_type"] == "billing.invoice.paid"
    assert line["event_id"] == str(unknown)
    held_back = bench.sample(
        "whisperer_outbox_held_back_total", home="ru", reason="unknown_event_type"
    )
    assert held_back == 1


async def test_a_delivery_task_missing_from_the_process_holds_the_event_back(
    valkey: Redis, homes: DatabaseAccess
) -> None:
    bench = event_bench(valkey, homes, [recording("mail.welcome", Applied())])
    [event_id] = await write_notes(homes.transactions, bench.outbox, Home.EU, 1)
    without_deliveries = workbench(valkey, [])

    with captured_logs() as logs:
        result = await OutboxRelay(bench.resources, without_deliveries.system.sender).relay(Home.EU)

    assert result == RelayPass(held_back=[event_id])
    [line] = [line for line in logs.lines() if line["level"] == "error"]
    assert "UnregisteredTaskError" in line["exception"]
    held_back = bench.sample(
        "whisperer_outbox_held_back_total", home="eu", reason="unregistered_delivery"
    )
    assert held_back == 1
