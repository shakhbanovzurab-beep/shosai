"""The lifecycle middleware: log fields, interrupted runs, tick markers, odd messages."""

import asyncio

from redis.asyncio import Redis
from structlog.contextvars import clear_contextvars, get_contextvars
from taskiq import TaskiqMessage, TaskiqResult

from tests.core.observability.capture import captured_logs
from tests.core.tasks.workbench import (
    Probe,
    Runs,
    absent,
    declare,
    eventually,
    running,
    settled,
    workbench,
)
from whisperer.core.tasks.declaration import TaskKind
from whisperer.core.tasks.deliveries import Delivery, LeavePending
from whisperer.core.tasks.lifecycle import TaskLifecycle
from whisperer.core.tasks.queues import tick_key
from whisperer.core.tasks.ticks import TickMarkers

TASK = declare("probe.lifecycle")


def message_of(task_id: str, task_name: str = TASK.name, **labels: str) -> TaskiqMessage:
    return TaskiqMessage(
        task_id=task_id,
        task_name=task_name,
        labels=dict(labels),
        args=[],
        kwargs={"payload": Probe(note="x").model_dump(mode="json")},
    )


def failed_with(error: BaseException) -> TaskiqResult[None]:
    return TaskiqResult(is_err=True, return_value=None, execution_time=0.1, error=error)


async def test_a_run_carries_the_task_and_the_request_on_its_lines(valkey: Redis) -> None:
    bench = workbench(valkey, [Runs().handler(TASK)])
    lifecycle = TaskLifecycle(bench.broker(), bench.system.metrics, TickMarkers(valkey))

    try:
        await lifecycle.pre_execute(message_of("t-1", request_id="req-7"))
        assert get_contextvars() == {
            "task_name": TASK.name,
            "task_id": "t-1",
            "request_id": "req-7",
        }
    finally:
        clear_contextvars()


async def test_an_interrupted_run_stays_pending_and_is_reported(valkey: Redis) -> None:
    bench = workbench(valkey, [Runs().handler(TASK)])
    lifecycle = TaskLifecycle(bench.broker(), bench.system.metrics, TickMarkers(valkey))
    delivery = Delivery("1-0", "t-1", TASK, 1, taken_at=0.0)
    bench.broker().held.take(delivery)

    with captured_logs() as logs:
        await lifecycle.post_execute(message_of("t-1"), failed_with(asyncio.CancelledError()))

    assert delivery.settlement == LeavePending()
    runs = bench.sample(
        "whisperer_task_runs_total", queue="default", task=TASK.name, outcome="interrupted"
    )
    assert runs == 1
    [line] = logs.lines()
    assert line["outcome"] == "interrupted"
    assert "exception" not in line


async def test_a_run_the_worker_did_not_deliver_is_reported(valkey: Redis) -> None:
    bench = workbench(valkey, [])
    lifecycle = TaskLifecycle(bench.broker(), bench.system.metrics, TickMarkers(valkey))

    with captured_logs() as logs:
        await lifecycle.post_execute(message_of("stray"), failed_with(RuntimeError()))

    assert [line["message"] for line in logs.lines()] == [
        "Выполнена задача, которой нет среди выдач воркера"
    ]


async def test_a_tick_without_marker_parts_frees_its_marker(valkey: Redis) -> None:
    tick = declare("probe.sweep_all", kind=TaskKind.TICK)
    bench = workbench(valkey, [Runs().handler(tick)])

    async with running(bench.broker()):
        assert await bench.system.sender.send_tick(tick, Probe(note="весь обход"))
        await eventually(settled(bench, tick.name, "succeeded"))
        await eventually(absent(valkey, tick_key(tick.name)))


async def test_a_tick_with_an_unreadable_marker_leaves_it_to_expire(valkey: Redis) -> None:
    tick = declare("probe.sweep_odd", kind=TaskKind.TICK)
    bench = workbench(valkey, [Runs().handler(tick)])
    lifecycle = TaskLifecycle(bench.broker(), bench.system.metrics, TickMarkers(valkey))
    bench.broker().held.take(Delivery("1-0", "t-1", tick, 1, taken_at=0.0))
    odd = message_of("t-1", tick.name, tick_marker="ru:ру")
    done = TaskiqResult(is_err=False, return_value=None, execution_time=0.1)

    with captured_logs() as logs:
        await lifecycle.post_execute(odd, done)

    assert "Метка маркера такта не разобрана: маркер снимется по сроку" in [
        line["message"] for line in logs.lines()
    ]
