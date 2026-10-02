"""Leases: a live worker keeps its long tasks, a dead worker's tasks return, outages pass."""

import asyncio
from datetime import timedelta

from redis.asyncio import Redis
from redis.exceptions import ResponseError

from tests.core.kv.outages import closed_port, redis_url
from tests.core.observability.capture import captured_logs
from tests.core.tasks.workbench import (
    FAST,
    Probe,
    Runs,
    counted,
    declare,
    eventually,
    running,
    settled,
    stream_entries_of,
    workbench,
)
from whisperer.core.kv.connection import connect_redis
from whisperer.core.tasks.declaration import RETRY_TRANSIENT, TaskKind
from whisperer.core.tasks.queues import CONSUMER_GROUP, TaskQueue, stream_key
from whisperer.core.tasks.stream import TaskStream, as_text
from whisperer.core.tasks.worker import consume_queue

LEASE_SECONDS = FAST.lease.total_seconds()
QUEUE_KEY = stream_key(TaskQueue.DEFAULT)


async def deliveries_of(client: Redis) -> list[tuple[str, int]]:
    """(consumer, deliveries) of every pending message of the default queue."""
    try:
        entries = await client.xpending_range(QUEUE_KEY, CONSUMER_GROUP, "-", "+", 100)
    except ResponseError:
        # Воркер ещё не создал группу: выданных сообщений нет.
        return []
    return [(as_text(item["consumer"]), int(item["times_delivered"])) for item in entries]


async def taken_by_a_dead_worker(client: Redis) -> None:
    """A worker that read the next message and died without settling it."""
    dead = TaskStream(client, TaskQueue.DEFAULT, FAST, "worker-dead")
    await dead.ensure_group()
    assert await dead.read() is not None


async def test_a_long_task_is_not_redelivered_while_its_lease_is_renewed(valkey: Redis) -> None:
    runs = Runs()
    task = declare("probe.long", retry=RETRY_TRANSIENT)
    handler = runs.handler(task, seconds=LEASE_SECONDS * 3)
    first = workbench(valkey, [handler], consumer="worker-a")
    second = workbench(valkey, [handler], consumer="worker-b")

    async with running(first.broker()), running(second.broker()):
        await first.system.sender.send(task, Probe(note="долго"))
        await eventually(lambda: _has_pending(valkey))
        await asyncio.sleep(LEASE_SECONDS * 2)
        assert [count for _, count in await deliveries_of(valkey)] == [1]
        await eventually(settled(first, task.name, "succeeded"), within=LEASE_SECONDS * 4)

    assert runs.notes == ["долго"]
    assert (
        second.sample(
            "whisperer_task_runs_total", queue="default", task=task.name, outcome="succeeded"
        )
        == 0
    )
    assert await first.depth() == 0


async def test_a_dead_workers_task_is_run_again_by_another_worker(valkey: Redis) -> None:
    runs = Runs()
    task = declare("probe.orphan", retry=RETRY_TRANSIENT)
    bench = workbench(valkey, [runs.handler(task)])
    await bench.system.sender.send(task, Probe(note="сирота"))
    await taken_by_a_dead_worker(valkey)

    with captured_logs() as logs:
        async with running(bench.broker()):
            await eventually(settled(bench, task.name, "succeeded"))

    assert runs.notes == ["сирота"]
    [line] = [line for line in logs.lines() if line["message"] == "Задача выполнена"]
    assert line["delivery"] == 2


async def test_a_task_without_retries_abandoned_once_goes_to_the_dead_letter(
    valkey: Redis,
) -> None:
    runs = Runs()
    task = declare("probe.charge")
    bench = workbench(valkey, [runs.handler(task)])
    await bench.system.sender.send(task, Probe(note="списание"))
    await taken_by_a_dead_worker(valkey)

    async with running(bench.broker()):
        await eventually(
            counted(bench, "whisperer_task_dead_letters_total", queue="default", reason="abandoned")
        )

    assert runs.notes == []
    [entry] = await bench.dead_letters()
    assert entry["reason"] == "abandoned"
    assert entry["deliveries"] == 1
    assert entry["payload"] == {"note": "списание", "link": None}


async def test_an_abandoned_tick_is_dropped_without_running(valkey: Redis) -> None:
    runs = Runs()
    tick = declare("probe.sweep", kind=TaskKind.TICK)
    bench = workbench(valkey, [runs.handler(tick)])
    assert await bench.system.sender.send_tick(tick, Probe(note="обход"))
    await taken_by_a_dead_worker(valkey)

    async with running(bench.broker()):
        await eventually(settled(bench, tick.name, "dropped"))

    assert runs.notes == []
    assert await bench.dead_letters() == []
    assert await bench.depth() == 0


async def test_a_lease_taken_by_another_worker_is_reported_and_success_still_settles(
    valkey: Redis,
) -> None:
    runs = Runs()
    task = declare("probe.contested")
    bench = workbench(valkey, [runs.handler(task, seconds=LEASE_SECONDS)])

    async with running(bench.broker()):
        await bench.system.sender.send(task, Probe(note="спор"))
        await eventually(lambda: _has_pending(valkey))
        [(stream_id, _)] = await stream_entries_of(valkey, QUEUE_KEY)
        await valkey.xclaim(QUEUE_KEY, CONSUMER_GROUP, "worker-other", 0, [stream_id])
        await bench.broker().renew_leases()
        assert bench.sample("whisperer_task_leases_lost_total", queue="default") == 1
        await eventually(settled(bench, task.name, "succeeded"))

    assert await bench.depth() == 0


async def test_a_worker_waits_out_a_valkey_outage_without_stopping() -> None:
    client = connect_redis(redis_url(closed_port()), "whisperer-tests")
    bench = workbench(client, [])
    stop = asyncio.Event()
    worker = asyncio.create_task(consume_queue(bench.broker(), stop))

    await eventually(
        counted(bench, "whisperer_task_valkey_failures_total", queue="default", operation="prune")
    )
    await asyncio.sleep(FAST.outage_pause.total_seconds() * 3)
    assert not worker.done()
    stop.set()
    await asyncio.wait_for(worker, 5)
    await client.aclose()


async def test_a_vanished_group_is_recreated_and_new_tasks_run(valkey: Redis) -> None:
    runs = Runs()
    task = declare("probe.after_reset")
    bench = workbench(valkey, [runs.handler(task)])

    async with running(bench.broker()):
        await bench.system.sender.send(task, Probe(note="до"))
        await eventually(settled(bench, task.name, "succeeded"))
        await valkey.flushdb()
        await bench.system.sender.send(task, Probe(note="после"))
        await eventually(settled(bench, task.name, "succeeded", at_least=2))

    assert runs.notes == ["до", "после"]


async def test_stopping_waits_for_the_running_task(valkey: Redis) -> None:
    runs = Runs()
    task = declare("probe.draining")
    bench = workbench(valkey, [runs.handler(task, seconds=0.3)])

    async with running(bench.broker(), drain=timedelta(seconds=5)) as stop:
        await bench.system.sender.send(task, Probe(note="дожать"))
        await eventually(lambda: _has_pending(valkey))
        stop.set()

    assert (
        bench.sample(
            "whisperer_task_runs_total", queue="default", task=task.name, outcome="succeeded"
        )
        == 1
    )
    assert await bench.depth() == 0


async def _has_pending(client: Redis) -> bool:
    return bool(await deliveries_of(client))
