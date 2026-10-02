"""Settling when Valkey is out loses nothing: the message stays pending and the failure counts."""

from datetime import timedelta

import pytest
from prometheus_client import CollectorRegistry
from redis.asyncio import Redis

from tests.core.kv.outages import closed_port, redis_url
from tests.core.observability.capture import captured_logs
from tests.core.tasks.workbench import FAST, declare
from whisperer.core.kv.connection import connect_redis
from whisperer.core.tasks.dead_letter import unparseable_entry
from whisperer.core.tasks.deliveries import (
    Acknowledge,
    Delivery,
    LeavePending,
    MoveToDeadLetter,
    RetryLater,
    Settlement,
)
from whisperer.core.tasks.metrics import TaskMetrics
from whisperer.core.tasks.queues import TaskQueue
from whisperer.core.tasks.settling import DeliverySettler, QueueFailures
from whisperer.core.tasks.stream import TaskStream

TASK = declare("probe.settled")
RETRY = RetryLater(timedelta(milliseconds=100))
DEAD = MoveToDeadLetter(unparseable_entry(TaskQueue.DEFAULT, 1))


def settler_over(client: Redis) -> tuple[DeliverySettler, CollectorRegistry]:
    registry = CollectorRegistry()
    metrics = TaskMetrics(registry)
    stream = TaskStream(client, TaskQueue.DEFAULT, FAST, "worker-a")
    return DeliverySettler(stream, metrics, QueueFailures(stream, metrics)), registry


def delivery_settled_as(settlement: Settlement | None) -> Delivery:
    return Delivery("1-0", "t-1", TASK, 1, taken_at=0.0, settlement=settlement)


@pytest.mark.parametrize(
    ("settlement", "operation"),
    [(Acknowledge(), "acknowledge"), (RETRY, "retry"), (DEAD, "dead_letter")],
)
async def test_a_settlement_valkey_does_not_take_is_counted_not_raised(
    settlement: Settlement, operation: str
) -> None:
    client = connect_redis(redis_url(closed_port()), "whisperer-tests")
    settler, registry = settler_over(client)

    await settler.settle(delivery_settled_as(settlement))

    failures = registry.get_sample_value(
        "whisperer_task_valkey_failures_total", {"queue": "default", "operation": operation}
    )
    assert failures == 1
    await client.aclose()


async def test_an_interrupted_run_is_left_for_another_worker_without_a_call() -> None:
    client = connect_redis(redis_url(closed_port()), "whisperer-tests")
    settler, registry = settler_over(client)

    await settler.settle(delivery_settled_as(LeavePending()))

    assert (
        registry.get_sample_value(
            "whisperer_task_valkey_failures_total", {"queue": "default", "operation": "acknowledge"}
        )
        is None
    )
    await client.aclose()


async def test_a_run_without_a_decision_is_reported(valkey: Redis) -> None:
    settler, _ = settler_over(valkey)

    with captured_logs() as logs:
        await settler.settle(delivery_settled_as(None))

    [line] = logs.lines()
    assert line["message"] == "Выдача завершилась без решения: сообщение вернётся после аренды"
    assert line["level"] == "error"


async def test_a_retry_of_a_message_another_worker_holds_is_not_scheduled(valkey: Redis) -> None:
    settler, _ = settler_over(valkey)
    other = TaskStream(valkey, TaskQueue.DEFAULT, FAST, "worker-b")
    await other.ensure_group()
    stream_id = await other.enqueue(b"held elsewhere")
    assert await other.read() is not None

    with captured_logs() as logs:
        await settler.settle(Delivery(stream_id, "t-1", TASK, 1, 0.0, settlement=RETRY))

    assert [line["message"] for line in logs.lines()] == [
        "Повтор не назначен: сообщение уже у другого воркера"
    ]
