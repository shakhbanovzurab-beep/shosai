"""The process metrics registry and the metrics of the observability pipeline itself.

Each process owns one registry, passed to whoever registers metrics; nothing registers
into the global default registry. Labels stay bounded (§16.7): role and process identity
come from the scrape target, user and company ids never become labels.
"""

from typing import Literal

from prometheus_client import CollectorRegistry, Counter, Histogram
from prometheus_client.gc_collector import GCCollector
from prometheus_client.platform_collector import PlatformCollector
from prometheus_client.process_collector import ProcessCollector

type TelemetrySignal = Literal["logs", "traces"]
type DropReason = Literal["queue_full", "export_failed", "shutdown"]

# Задержка цикла событий: от единиц миллисекунд (норма) до секунд (блокирующий вызов).
LOOP_LAG_BUCKETS = (0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)


def build_metrics_registry() -> CollectorRegistry:
    """A registry with the standard process, platform and garbage-collector metrics."""
    registry = CollectorRegistry()
    ProcessCollector(registry=registry)
    PlatformCollector(registry=registry)
    GCCollector(registry=registry)
    return registry


class ObservabilityMetrics:
    """Telemetry drops and event-loop lag of one process."""

    def __init__(self, registry: CollectorRegistry) -> None:
        self._telemetry_dropped = Counter(
            "shosai_telemetry_dropped",
            "Записи логов и спаны, отброшенные без доставки",
            ("signal", "reason"),
            registry=registry,
        )
        # Гистограмма, а не датчик последнего значения: всплеск между двумя опросами
        # Prometheus иначе не виден.
        self.event_loop_lag = Histogram(
            "shosai_event_loop_lag_seconds",
            "Опоздание цикла событий против запланированного пробуждения",
            buckets=LOOP_LAG_BUCKETS,
            registry=registry,
        )

    def count_dropped(self, signal: TelemetrySignal, reason: DropReason, count: int = 1) -> None:
        """Count log records or spans that left the process undelivered."""
        self._telemetry_dropped.labels(signal=signal, reason=reason).inc(count)
