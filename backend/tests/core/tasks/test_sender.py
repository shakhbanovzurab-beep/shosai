"""Sending: one message per task, 503 instead of waiting or losing, ticks never overlap."""

import time
from http import HTTPStatus

import pytest
from redis.asyncio import Redis
from taskiq import TaskiqMessage

from shosai.core.kv.connection import connect_redis
from shosai.core.observability.log_context import log_context
from shosai.core.tasks.declaration import TaskKind
from shosai.core.tasks.errors import TaskQueueUnavailableError, UnregisteredTaskError
from shosai.core.tasks.queues import TaskQueue, stream_key, tick_key
from tests.core.kv.outages import closed_port, redis_url, silent_server
from tests.core.tasks.workbench import Probe, Runs, declare, stream_entries_of, workbench

REPORT = declare("probe.report", queue=TaskQueue.CRITICAL)
SWEEP = declare("probe.sweep", kind=TaskKind.TICK)
FILLER = declare("probe.filler")
RUNS = Runs()
HANDLERS = (RUNS.handler(REPORT), RUNS.handler(SWEEP), RUNS.handler(FILLER))


async def stored(client: Redis, queue: TaskQueue) -> list[TaskiqMessage]:
    entries = await stream_entries_of(client, stream_key(queue))
    return [TaskiqMessage.model_validate_json(fields[b"data"]) for _, fields in entries]


async def test_a_task_is_one_message_with_its_payload_and_request(valkey: Redis) -> None:
    bench = workbench(valkey, HANDLERS)

    with log_context(request_id="req-42"):
        task_id = await bench.system.sender.send(REPORT, Probe(note="квартал"))

    [message] = await stored(valkey, TaskQueue.CRITICAL)
    assert message.task_id == task_id
    assert len(task_id) == 32
    assert message.task_name == REPORT.name
    assert message.args == []
    assert message.kwargs == {"payload": {"note": "квартал", "link": None}}
    assert message.labels["request_id"] == "req-42"
    assert bench.sample("shosai_tasks_sent_total", queue="critical", task=REPORT.name) == 1


async def test_a_task_this_process_does_not_handle_is_refused(valkey: Redis) -> None:
    bench = workbench(valkey, HANDLERS)
    impostor = declare(REPORT.name, queue=TaskQueue.CRITICAL)

    with pytest.raises(UnregisteredTaskError):
        await bench.system.sender.send(impostor, Probe(note="x"))
    with pytest.raises(UnregisteredTaskError):
        await bench.system.sender.send(declare("probe.unknown"), Probe(note="x"))
    assert await valkey.exists(stream_key(TaskQueue.CRITICAL)) == 0


async def test_a_payload_of_another_model_is_refused(valkey: Redis) -> None:
    bench = workbench(valkey, HANDLERS)

    with pytest.raises(TypeError):
        await bench.system.sender.send(REPORT, object())  # type: ignore[type-var]


async def test_ticks_and_work_go_through_their_own_methods(valkey: Redis) -> None:
    sender = workbench(valkey, HANDLERS).system.sender

    with pytest.raises(ValueError, match="send_tick"):
        await sender.send(SWEEP, Probe(note="x"))
    with pytest.raises(ValueError, match="не такт"):
        await sender.send_tick(REPORT, Probe(note="x"))


async def test_a_full_queue_answers_503_and_keeps_its_tasks(valkey: Redis) -> None:
    bench = workbench(valkey, HANDLERS, capacity=1)
    await bench.system.sender.send(REPORT, Probe(note="первая"))

    with pytest.raises(TaskQueueUnavailableError) as refused:
        await bench.system.sender.send(REPORT, Probe(note="вторая"))

    assert refused.value.code == "queue_unavailable"
    assert refused.value.status is HTTPStatus.SERVICE_UNAVAILABLE
    assert refused.value.params == {"retry_after_seconds": 5}
    assert [m.kwargs["payload"]["note"] for m in await stored(valkey, TaskQueue.CRITICAL)] == [
        "первая"
    ]
    assert bench.sample("shosai_task_send_failures_total", queue="critical", reason="full") == 1


async def test_a_silent_valkey_answers_503_within_the_enqueue_deadline() -> None:
    async with silent_server() as port:
        client = connect_redis(redis_url(port), "shosai-tests")
        bench = workbench(client, HANDLERS)
        started = time.monotonic()

        with pytest.raises(TaskQueueUnavailableError):
            await bench.system.sender.send(REPORT, Probe(note="x"))

        assert time.monotonic() - started < 0.5
        await client.aclose()
    failures = bench.sample(
        "shosai_task_send_failures_total", queue="critical", reason="unavailable"
    )
    assert failures == 1


async def test_a_stopped_valkey_answers_503_for_a_tick() -> None:
    client = connect_redis(redis_url(closed_port()), "shosai-tests")
    bench = workbench(client, HANDLERS)

    with pytest.raises(TaskQueueUnavailableError):
        await bench.system.sender.send_tick(SWEEP, Probe(note="x"))
    await client.aclose()


async def test_a_tick_is_skipped_while_the_previous_one_is_in_flight(valkey: Redis) -> None:
    bench = workbench(valkey, HANDLERS)
    sender = bench.system.sender

    assert await sender.send_tick(SWEEP, Probe(note="ru"), "ru")
    assert not await sender.send_tick(SWEEP, Probe(note="ru"), "ru")
    assert await sender.send_tick(SWEEP, Probe(note="eu"), "eu")

    [first, second] = await stored(valkey, TaskQueue.DEFAULT)
    assert first.labels["tick_marker"] == "ru"
    assert await valkey.get(tick_key(SWEEP.name, "ru")) == first.task_id.encode()
    assert second.labels["tick_marker"] == "eu"
    assert bench.sample("shosai_task_ticks_skipped_total", task=SWEEP.name) == 1
    ttl = await valkey.pttl(tick_key(SWEEP.name, "ru"))
    assert SWEEP.deadline.total_seconds() * 1000 < ttl <= SWEEP.hold_limit.total_seconds() * 1000


async def test_a_tick_that_could_not_be_queued_does_not_block_the_next(valkey: Redis) -> None:
    bench = workbench(valkey, HANDLERS, capacity=1)
    await bench.system.sender.send(FILLER, Probe(note="занимает очередь"))

    with pytest.raises(TaskQueueUnavailableError):
        await bench.system.sender.send_tick(SWEEP, Probe(note="x"), "ru")

    assert await valkey.exists(tick_key(SWEEP.name, "ru")) == 0
