"""Queue gauges: depth, the oldest task's age and the dead letter, in one round trip."""

import time

from prometheus_client import CollectorRegistry
from redis.asyncio import Redis

from shosai.core.kv.connection import connect_redis
from shosai.core.tasks.metrics import TaskMetrics
from shosai.core.tasks.monitor import QueueMonitor
from shosai.core.tasks.queues import TaskQueue, dead_letter_key
from tests.core.kv.outages import closed_port, redis_url
from tests.core.tasks.workbench import Probe, Runs, declare, workbench

TASK = declare("probe.monitored", queue=TaskQueue.BULK)


def gauge(registry: CollectorRegistry, name: str, queue: str) -> float | None:
    return registry.get_sample_value(name, {"queue": queue})


async def test_gauges_show_the_backlog_and_the_dead_letter(valkey: Redis) -> None:
    bench = workbench(valkey, [Runs().handler(TASK)])
    await bench.system.sender.send(TASK, Probe(note="первая"))
    await bench.system.sender.send(TASK, Probe(note="вторая"))
    await valkey.xadd(dead_letter_key(TaskQueue.BULK), {"entry": "{}"})
    now = time.time()
    monitor = QueueMonitor(valkey, bench.system.metrics, clock=lambda: now + 30)

    assert await monitor.refresh()

    registry = bench.registry
    assert gauge(registry, "shosai_task_queue_depth", "bulk") == 2
    age = gauge(registry, "shosai_task_queue_oldest_age_seconds", "bulk") or 0
    assert 29 < age < 31
    assert gauge(registry, "shosai_task_dead_letter_entries", "bulk") == 1
    newest = gauge(registry, "shosai_task_dead_letter_newest_timestamp_seconds", "bulk") or 0
    assert now - 1 < newest <= now + 1
    assert gauge(registry, "shosai_task_queue_depth", "critical") == 0
    assert gauge(registry, "shosai_task_queue_oldest_age_seconds", "critical") == 0
    assert gauge(registry, "shosai_task_dead_letter_newest_timestamp_seconds", "critical") == 0


async def test_a_silent_valkey_leaves_the_gauges_and_is_counted() -> None:
    registry = CollectorRegistry()
    metrics = TaskMetrics(registry)
    client = connect_redis(redis_url(closed_port()), "shosai-tests")

    assert not await QueueMonitor(client, metrics).refresh()

    assert gauge(registry, "shosai_task_queue_depth", "default") is None
    failures = registry.get_sample_value(
        "shosai_task_valkey_failures_total", {"queue": "default", "operation": "monitor"}
    )
    assert failures == 1
    await client.aclose()
