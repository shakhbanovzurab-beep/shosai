"""The broker's own duties: leases past their limit, renewal failures, one run per task."""

import asyncio
import os
import socket

import pytest
from prometheus_client import CollectorRegistry
from redis.asyncio import Redis

from shosai.core.kv.connection import connect_redis
from shosai.core.tasks.broker import ValkeyStreamBroker, new_consumer_name
from shosai.core.tasks.deliveries import Delivery
from shosai.core.tasks.metrics import TaskMetrics
from shosai.core.tasks.queues import TaskQueue
from shosai.core.tasks.stream import TaskStream
from tests.core.kv.outages import closed_port, redis_url
from tests.core.observability.capture import captured_logs
from tests.core.tasks.workbench import FAST, Probe, Runs, declare, eventually, workbench

TASK = declare("probe.brokered")


def broker_over(client: Redis, clock: list[float]) -> tuple[ValkeyStreamBroker, CollectorRegistry]:
    registry = CollectorRegistry()
    stream = TaskStream(client, TaskQueue.DEFAULT, FAST, "worker-a")
    return ValkeyStreamBroker(stream, TaskMetrics(registry), clock=lambda: clock[0]), registry


def test_a_consumer_is_named_by_host_and_process() -> None:
    name = new_consumer_name()

    assert name.startswith(f"{socket.gethostname()}-{os.getpid()}-")
    assert name != new_consumer_name()


def test_a_broker_registers_a_task_once(valkey: Redis) -> None:
    broker, _ = broker_over(valkey, [0.0])
    broker.register(Runs().handler(TASK))

    with pytest.raises(ValueError, match="дважды"):
        broker.register(Runs().handler(TASK))


async def test_a_delivery_held_past_its_limit_loses_its_lease(valkey: Redis) -> None:
    clock = [0.0]
    broker, registry = broker_over(valkey, clock)
    delivery = Delivery("1-0", "t-1", TASK, 1, taken_at=0.0)
    broker.held.take(delivery)
    clock[0] = TASK.hold_limit.total_seconds() + 1

    with captured_logs() as logs:
        await broker.renew_leases()

    assert not delivery.renewing
    assert registry.get_sample_value("shosai_task_leases_capped_total", {"queue": "default"}) == 1
    assert [line["level"] for line in logs.lines()] == ["error"]


async def test_a_renewal_valkey_does_not_take_is_counted() -> None:
    client = connect_redis(redis_url(closed_port()), "shosai-tests")
    broker, registry = broker_over(client, [0.0])
    broker.held.take(Delivery("1-0", "t-1", TASK, 1, taken_at=0.0))

    await broker.renew_leases()

    failures = registry.get_sample_value(
        "shosai_task_valkey_failures_total", {"queue": "default", "operation": "renew"}
    )
    assert failures == 1
    await client.aclose()


class FailingRenewal(ValkeyStreamBroker):
    """A broker whose every renewal pass fails."""

    passes = 0

    async def renew_leases(self) -> None:
        self.passes += 1
        message = "сбой прохода"
        raise RuntimeError(message)


async def test_a_failing_renewal_pass_is_logged_and_the_next_one_runs(valkey: Redis) -> None:
    stream = TaskStream(valkey, TaskQueue.DEFAULT, FAST, "worker-a")
    broker = FailingRenewal(stream, TaskMetrics(CollectorRegistry()))
    broker.is_worker_process = True

    async def two_passes() -> bool:
        return broker.passes >= 2

    with captured_logs() as logs:
        await broker.startup()
        try:
            await eventually(two_passes)
        finally:
            await broker.shutdown()

    failed = [line for line in logs.lines() if line["message"] == "Проход продления аренды упал"]
    assert len(failed) >= 2
    assert "RuntimeError: сбой прохода" in failed[0]["exception"]


async def test_a_task_already_running_here_is_not_delivered_twice(valkey: Redis) -> None:
    bench = workbench(valkey, [Runs().handler(TASK)])
    broker = bench.broker()
    await bench.system.sender.send(TASK, Probe(note="одна"))
    deliveries = broker.listen()

    first = await asyncio.wait_for(anext(deliveries), 5)
    await asyncio.sleep(FAST.lease.total_seconds() + 0.1)
    with pytest.raises(TimeoutError):
        await asyncio.wait_for(anext(deliveries), FAST.recover_every.total_seconds() * 4)

    assert len(broker.held) == 1
    assert first.data
    assert await bench.dead_letters() == []
    assert await bench.depth() == 1
    await deliveries.aclose()
