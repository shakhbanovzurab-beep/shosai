"""The loop-lag watcher sees a blocking call; the registry carries the process metrics."""

import asyncio
import contextlib
import time

from prometheus_client import CollectorRegistry

from whisperer.core.observability.loop_lag import watch_event_loop_lag
from whisperer.core.observability.metrics import ObservabilityMetrics, build_metrics_registry

BLOCKING_SECONDS = 0.2


async def test_a_blocking_call_shows_as_loop_lag() -> None:
    registry = CollectorRegistry()
    metrics = ObservabilityMetrics(registry)
    watcher = asyncio.create_task(watch_event_loop_lag(metrics.event_loop_lag, interval=0.01))
    await asyncio.sleep(0.05)

    # Синхронный вызов в цикле событий — ровно та ошибка, которую должен увидеть сторож.
    asyncio.get_running_loop().call_soon(time.sleep, BLOCKING_SECONDS)
    await asyncio.sleep(0.1)
    watcher.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await watcher

    total_lag = registry.get_sample_value("whisperer_event_loop_lag_seconds_sum")
    assert total_lag is not None
    assert total_lag >= BLOCKING_SECONDS * 0.75
    largest_normal = registry.get_sample_value(
        "whisperer_event_loop_lag_seconds_bucket", {"le": "0.1"}
    )
    observed = registry.get_sample_value("whisperer_event_loop_lag_seconds_count")
    assert largest_normal is not None
    assert observed is not None
    assert observed - largest_normal >= 1


def test_the_registry_carries_process_metrics() -> None:
    registry = build_metrics_registry()

    assert registry.get_sample_value("process_resident_memory_bytes")
    assert registry.get_sample_value("python_gc_collections_total", {"generation": "0"}) is not None
