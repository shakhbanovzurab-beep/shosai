"""A worker runs each task to its settlement: done, retried, dead-lettered or dropped."""

from datetime import timedelta

from pydantic import SecretStr
from redis.asyncio import Redis

from shosai.core.tasks.declaration import MAX_DELIVERIES, RETRY_TRANSIENT, TaskKind
from shosai.core.tasks.queues import stream_key, tick_key
from tests.core.observability.capture import captured_logs
from tests.core.tasks.workbench import (
    Probe,
    Runs,
    absent,
    counted,
    declare,
    eventually,
    running,
    settled,
    workbench,
)

LINK = "https://whisperer.one/reset?token=very-secret"
RUNS_TOTAL = "shosai_task_runs_total"


async def test_a_finished_task_runs_once_and_leaves_the_queue(valkey: Redis) -> None:
    runs = Runs()
    task = declare("probe.done")
    bench = workbench(valkey, [runs.handler(task)])

    with captured_logs() as logs:
        async with running(bench.broker()):
            await bench.system.sender.send(task, Probe(note="готово"))
            await eventually(settled(bench, task.name, "succeeded"))

    assert runs.notes == ["готово"]
    assert await bench.depth() == 0
    [line] = [line for line in logs.lines() if line["message"] == "Задача выполнена"]
    assert line["task_name"] == task.name
    assert line["outcome"] == "succeeded"
    assert line["delivery"] == 1


async def test_the_fifth_failed_delivery_lands_in_the_dead_letter_with_secrets_hidden(
    valkey: Redis,
) -> None:
    runs = Runs()
    task = declare("probe.flaky", retry=RETRY_TRANSIENT)
    bench = workbench(valkey, [runs.handler(task, failure=ConnectionError("нет связи"))])

    with captured_logs() as logs:
        async with running(bench.broker()):
            await bench.system.sender.send(task, Probe(note="сброс", link=SecretStr(LINK)))
            await eventually(settled(bench, task.name, "dead_lettered"))

    assert runs.notes == ["сброс"] * MAX_DELIVERIES
    assert bench.sample(RUNS_TOTAL, queue="default", task=task.name, outcome="retried") == 4
    [entry] = await bench.dead_letters()
    assert entry["reason"] == "failed"
    assert entry["deliveries"] == MAX_DELIVERIES
    assert entry["error_type"] == "builtins.ConnectionError"
    assert entry["payload"] == {"note": "сброс", "link": "***"}
    assert entry["payload_masked"] is True
    assert bench.sample("shosai_task_dead_letters_total", queue="default", reason="failed") == 1
    assert await bench.depth() == 0
    assert "very-secret" not in logs.text()
    failures = [line for line in logs.lines() if line.get("task_name") == task.name]
    assert [line["outcome"] for line in failures] == ["retried"] * 4 + ["dead_lettered"]
    assert all("ConnectionError: нет связи" in line["exception"] for line in failures)
    assert "Exception found while executing function." not in logs.text()


async def test_a_failure_that_another_delivery_cannot_fix_is_dead_lettered_at_once(
    valkey: Redis,
) -> None:
    runs = Runs()
    task = declare("probe.broken", retry=RETRY_TRANSIENT)
    bench = workbench(valkey, [runs.handler(task, failure=ValueError("ошибка в данных"))])

    async with running(bench.broker()):
        await bench.system.sender.send(task, Probe(note="один раз"))
        await eventually(settled(bench, task.name, "dead_lettered"))

    assert runs.notes == ["один раз"]
    [entry] = await bench.dead_letters()
    assert entry["deliveries"] == 1
    assert entry["error_type"] == "builtins.ValueError"


async def test_a_payload_that_does_not_match_is_dead_lettered_without_its_values(
    valkey: Redis,
) -> None:
    runs = Runs()
    task = declare("probe.strict", retry=RETRY_TRANSIENT)
    bench = workbench(valkey, [runs.handler(task)])
    message = (
        b'{"task_id":"t-1","task_name":"probe.strict","labels":{},"args":[],'
        b'"kwargs":{"payload":{"email":"user@example.com"}}}'
    )
    await valkey.xadd(stream_key(task.queue), {"data": message})

    async with running(bench.broker()):
        await eventually(settled(bench, task.name, "dead_lettered"))

    assert runs.notes == []
    [entry] = await bench.dead_letters()
    assert entry["error_type"] == "shosai.core.tasks.errors.InvalidTaskPayloadError"
    assert entry["error"] == "данные задачи probe.strict не прошли проверку: note: missing"
    assert entry["payload"] is None


async def test_a_run_past_its_deadline_is_stopped_and_retried(valkey: Redis) -> None:
    runs = Runs()
    task = declare("probe.slow", retry=RETRY_TRANSIENT, deadline=timedelta(milliseconds=100))
    bench = workbench(valkey, [runs.handler(task, seconds=5)])

    async with running(bench.broker()):
        await bench.system.sender.send(task, Probe(note="медленно"))
        await eventually(settled(bench, task.name, "retried", at_least=2))

    assert bench.sample(RUNS_TOTAL, queue="default", task=task.name, outcome="succeeded") == 0


async def test_an_unknown_task_is_dead_lettered_andcounted(valkey: Redis) -> None:
    task = declare("probe.newer")
    producer = workbench(valkey, [Runs().handler(task)], consumer="producer")
    worker = workbench(valkey, [], consumer="older-worker")
    await producer.system.sender.send(task, Probe(note="user@example.com"))

    async with running(worker.broker()):
        await eventually(counted(worker, "shosai_task_unknown_total", queue="default"))

    [entry] = await worker.dead_letters()
    assert entry["reason"] == "unknown_task"
    assert entry["task"] == task.name
    assert entry["payload"] is None
    assert "user@example.com" not in str(entry)
    dead = worker.sample("shosai_task_dead_letters_total", queue="default", reason="unknown_task")
    assert dead == 1
    assert await worker.depth() == 0


async def test_a_message_that_is_not_a_task_is_dead_lettered(valkey: Redis) -> None:
    bench = workbench(valkey, [])
    await valkey.xadd(stream_key(declare("probe.any").queue), {"data": b"\xff not json"})

    async with running(bench.broker()):
        await eventually(
            counted(bench, "shosai_task_dead_letters_total", queue="default", reason="unparseable")
        )

    [entry] = await bench.dead_letters()
    assert entry["reason"] == "unparseable"
    assert await bench.depth() == 0


async def test_a_failed_tick_is_dropped_and_frees_its_marker(valkey: Redis) -> None:
    runs = Runs()
    tick = declare("probe.sweep", kind=TaskKind.TICK)
    bench = workbench(valkey, [runs.handler(tick, failure=RuntimeError("сбой обхода"))])

    async with running(bench.broker()):
        assert await bench.system.sender.send_tick(tick, Probe(note="обход"), "ru")
        await eventually(settled(bench, tick.name, "dropped"))
        await eventually(absent(valkey, tick_key(tick.name, "ru")))
        assert await bench.system.sender.send_tick(tick, Probe(note="следующий"), "ru")
        await eventually(settled(bench, tick.name, "dropped", at_least=2))

    assert runs.notes == ["обход", "следующий"]
    assert await bench.dead_letters() == []
