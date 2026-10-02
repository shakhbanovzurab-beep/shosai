"""The telemetry of one process: logs, the metrics registry, the tracer provider, loop lag.

Logging is configured first, so every later step, its failure included, is a JSON line.
At stop the tracer provider exports what it can within its budget and the log queue is
written out last, so the lines of the stop itself are not lost.
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from opentelemetry.sdk.trace import TracerProvider
from prometheus_client import CollectorRegistry

from whisperer.core.config.loading import Settings
from whisperer.core.config.roles import ProcessRole
from whisperer.core.observability.logs import configure_logging
from whisperer.core.observability.loop_lag import watch_event_loop_lag
from whisperer.core.observability.metrics import ObservabilityMetrics, build_metrics_registry
from whisperer.core.observability.tracing import build_tracer_provider


@dataclass(frozen=True, slots=True)
class ProcessTelemetry:
    """Where the process reports: one metrics registry and one tracer provider."""

    registry: CollectorRegistry
    tracer_provider: TracerProvider


@asynccontextmanager
async def open_telemetry(settings: Settings, role: ProcessRole) -> AsyncIterator[ProcessTelemetry]:
    """Logs, metrics and traces of the process until the block ends, then flushed."""
    registry = build_metrics_registry()
    metrics = ObservabilityMetrics(registry)
    logging_pipeline = configure_logging(settings.observability, role, metrics)
    try:
        provider = build_tracer_provider(
            settings.observability, settings.environment, role, metrics
        )
        lag = asyncio.create_task(watch_event_loop_lag(metrics.event_loop_lag), name="loop-lag")
        try:
            yield ProcessTelemetry(registry=registry, tracer_provider=provider)
        finally:
            lag.cancel()
            # Ждать конца наблюдателя, не поднимая его отмену: внешнюю отмену это не глотает.
            await asyncio.wait({lag})
            # Выгрузка спанов ждёт коллектор не дольше бюджета; цикл событий она не держит.
            await asyncio.to_thread(provider.shutdown)
    finally:
        logging_pipeline.close()
