"""An event committed with its effect is applied once by each subscriber (§8.1, §12)."""

import uuid

import pytest
import sqlalchemy as sa
from redis.asyncio import Redis

from tests.core.events.bench import (
    Applied,
    EventBench,
    NoteState,
    NoteWritten,
    effect_id,
    event_bench,
    outbox_rows,
    recording,
    runs,
)
from tests.core.events.relay_bench import RecordingSender
from tests.core.observability.capture import captured_logs
from tests.core.tasks.workbench import eventually, running
from tests.harness.connections import fetch_rows, fetch_value
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot
from whisperer.core.events.relay import OutboxRelay
from whisperer.core.events.system import RELAY_OUTBOX
from whisperer.core.kernel.homes import Home
from whisperer.core.kernel.tenancy import TenancyScope
from whisperer.core.tasks.payloads import HomeTaskPayload
from whisperer.core.tasks.queues import TaskQueue

USER_ID = uuid.UUID("0190f0f0-0000-7000-8000-00000000000a")
ORG_ID = uuid.UUID("0190f0f0-0000-7000-8000-00000000000b")
MAIL = "mail.welcome"
INDEX = "search.index_note"


async def write_note_with_effect(
    bench: EventBench, homes: DatabaseAccess, table: sa.TableClause, home: Home
) -> uuid.UUID:
    """The producer's transaction: its own row and the event about it, in a company's scope."""
    record_id = uuid.uuid4()
    async with homes.transactions.begin(TenancyScope(home, USER_ID, ORG_ID)) as session:
        await session.execute(sa.insert(table).values(id=record_id, org_id=ORG_ID, note="note"))
        return await bench.outbox.add(
            session, NoteWritten(record_id=record_id, state=NoteState.FINAL)
        )


@pytest.mark.parametrize("home", list(Home))
async def test_an_event_committed_with_its_effect_reaches_each_subscriber_once(
    valkey: Redis,
    homes: DatabaseAccess,
    probe_table: sa.TableClause,
    run_slot: RunSlot,
    home: Home,
) -> None:
    applied = Applied()
    subscribers = [
        recording(MAIL, applied, queue=TaskQueue.CRITICAL),
        recording(INDEX, applied),
    ]
    bench = event_bench(valkey, homes, subscribers)
    event_id = await write_note_with_effect(bench, homes, probe_table, home)

    async with running(bench.tasks.broker(TaskQueue.CRITICAL)), running(bench.tasks.broker()):
        await bench.tasks.system.sender.send_tick(
            RELAY_OUTBOX, HomeTaskPayload(home=home), home.value
        )
        await eventually(runs(bench, TaskQueue.CRITICAL, f"events.{MAIL}", "succeeded"))
        await eventually(runs(bench, TaskQueue.DEFAULT, f"events.{INDEX}", "succeeded"))

    connection = run_slot.claimed.connections[home]
    assert sorted(applied.consumers()) == [MAIL, INDEX]
    assert {received.event_id for _, received in applied.events} == {event_id}
    assert {received.scope for _, received in applied.events} == {
        TenancyScope(home, USER_ID, ORG_ID)
    }
    marks = await fetch_rows(connection, "SELECT consumer, event_id FROM processed_events")
    assert sorted((mark["consumer"], mark["event_id"]) for mark in marks) == [
        (MAIL, event_id),
        (INDEX, event_id),
    ]
    effects = await fetch_rows(
        connection, "SELECT id, org_id FROM probe_records WHERE note <> 'note'"
    )
    assert sorted((row["id"], row["org_id"]) for row in effects) == sorted(
        (effect_id(received, consumer), ORG_ID) for consumer, received in applied.events
    )
    [row] = await outbox_rows(connection)
    assert row["published"]


async def test_a_redelivered_event_does_not_run_the_handler_again(
    valkey: Redis, homes: DatabaseAccess, probe_table: sa.TableClause, run_slot: RunSlot
) -> None:
    applied = Applied()
    bench = event_bench(valkey, homes, [recording(INDEX, applied)])
    await write_note_with_effect(bench, homes, probe_table, Home.RU)
    captured = RecordingSender(homes.databases)
    await OutboxRelay(bench.resources, captured).relay(Home.RU)
    [(_, payload)] = captured.sent
    [route] = bench.resources.catalog.all_routes()

    with captured_logs() as logs:
        async with running(bench.tasks.broker()):
            for _ in range(2):
                await bench.tasks.system.sender.send(route.task, payload)
            await eventually(runs(bench, TaskQueue.DEFAULT, route.task.name, "succeeded", 2))

    connection = run_slot.claimed.connections[Home.RU]
    assert applied.consumers() == [INDEX]
    assert await fetch_value(connection, "SELECT count(*) FROM processed_events") == 1
    assert await fetch_value(connection, "SELECT count(*) FROM probe_records") == 2
    assert bench.sample("whisperer_event_duplicate_deliveries_total", consumer=INDEX) == 1
    [skipped] = [line for line in logs.lines() if line["message"].startswith("Событие уже")]
    assert (skipped["consumer"], skipped["event_id"]) == (INDEX, str(payload.event_id))


async def test_a_failed_handler_applies_nothing_and_its_retry_applies_the_event_once(
    valkey: Redis, homes: DatabaseAccess, probe_table: sa.TableClause, run_slot: RunSlot
) -> None:
    applied = Applied()
    flaky = recording(INDEX, applied, failures=[ConnectionError("сеть оборвалась")])
    bench = event_bench(valkey, homes, [flaky])
    await write_note_with_effect(bench, homes, probe_table, Home.EU)

    async with running(bench.tasks.broker()):
        await OutboxRelay(bench.resources, bench.tasks.system.sender).relay(Home.EU)
        await eventually(runs(bench, TaskQueue.DEFAULT, flaky.task_name, "succeeded"))

    connection = run_slot.claimed.connections[Home.EU]
    assert applied.consumers() == [INDEX, INDEX]
    assert (
        bench.sample(
            "whisperer_task_runs_total", queue="default", task=flaky.task_name, outcome="retried"
        )
        == 1
    )
    assert await fetch_value(connection, "SELECT count(*) FROM processed_events") == 1
    assert await fetch_value(connection, "SELECT count(*) FROM probe_records") == 2
