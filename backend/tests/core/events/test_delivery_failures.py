"""A delivery nobody can apply is dead-lettered and counted, never dropped (§14 rule 9, §16.4)."""

import json
import uuid
from datetime import UTC, datetime

import pytest
from redis.asyncio import Redis

from tests.core.events.bench import Applied, event_bench, insert_raw_event, recording, runs
from tests.core.tasks.workbench import counted, eventually, running
from tests.harness.connections import fetch_value
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot
from whisperer.core.events.delivery import EventDeliveryPayload, received_event
from whisperer.core.events.relay import OutboxRelay
from whisperer.core.kernel.homes import Home
from whisperer.core.tasks.errors import InvalidTaskPayloadError
from whisperer.core.tasks.queues import TaskQueue

INDEX = "search.index_note"


async def test_a_consumer_this_worker_does_not_know_is_dead_lettered_and_counted(
    valkey: Redis, homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    applied = Applied()
    producer = event_bench(valkey, homes, [recording(INDEX, applied)])
    worker = event_bench(valkey, homes)
    event_id = await insert_raw_event(run_slot.claimed.connections[Home.RU], "probe.note.written")

    await OutboxRelay(producer.resources, producer.tasks.system.sender).relay(Home.RU)
    async with running(worker.tasks.broker()):
        await eventually(counted(worker.tasks, "whisperer_task_unknown_total", queue="default"))

    [entry] = await worker.tasks.dead_letters()
    assert (entry["reason"], entry["task"]) == ("unknown_task", f"events.{INDEX}")
    assert entry["payload"] is None
    assert applied.events == []
    assert str(event_id) not in json.dumps(entry)


async def test_an_event_its_consumer_cannot_read_is_dead_lettered_without_running(
    valkey: Redis, homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    applied = Applied()
    subscription = recording(INDEX, applied)
    bench = event_bench(valkey, homes, [subscription])
    connection = run_slot.claimed.connections[Home.EU]
    # Строка без record_id и state: так её оставил бы производитель с несовместимой схемой.
    await insert_raw_event(connection, "probe.note.written")

    async with running(bench.tasks.broker()):
        await OutboxRelay(bench.resources, bench.tasks.system.sender).relay(Home.EU)
        await eventually(runs(bench, TaskQueue.DEFAULT, subscription.task_name, "dead_lettered"))

    [entry] = await bench.tasks.dead_letters()
    assert entry["reason"] == "failed"
    assert entry["error_type"] == "whisperer.core.tasks.errors.InvalidTaskPayloadError"
    assert "event.record_id: missing" in entry["error"]
    assert applied.events == []
    assert await fetch_value(connection, "SELECT count(*) FROM processed_events") == 0


def test_a_delivery_of_another_event_type_is_refused_before_the_handler() -> None:
    subscription = recording(INDEX, Applied())
    payload = EventDeliveryPayload(
        home=Home.RU,
        event_id=uuid.uuid7(),
        event_type="probe.note.archived",
        version=1,
        occurred_at=datetime.now(UTC),
        event={"record_id": str(uuid.uuid4()), "state": "draft"},
    )

    with pytest.raises(InvalidTaskPayloadError, match=r"event_type: expected probe\.note\.written"):
        received_event(subscription, payload)
