"""Traces: the process tracer provider and a bounded way out to the collector (§16.1).

Every span is recorded (the collector samples by tail), so log lines and task headers
always carry a trace context. Without `OTEL_EXPORTER_OTLP_ENDPOINT` nothing is exported.
With it, spans leave through a bounded queue: a span that does not fit, a batch the
collector refused and whatever is left after the shutdown budget are dropped and counted.
"""

import threading
import time
from collections.abc import Sequence
from importlib.metadata import version

from opentelemetry.context import Context
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION, Resource
from opentelemetry.sdk.trace import ReadableSpan, Span, SpanProcessor, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.sdk.trace.sampling import ALWAYS_ON
from pydantic import HttpUrl

from whisperer.core.config.roles import ProcessRole
from whisperer.core.config.sections import ObservabilitySettings
from whisperer.core.config.values import Environment
from whisperer.core.observability.metrics import ObservabilityMetrics

SPAN_QUEUE_CAPACITY = 2048
EXPORT_BATCH_SIZE = 512
EXPORT_DELAY_MILLIS = 2000
EXPORT_TIMEOUT_SECONDS = 5.0
SHUTDOWN_BUDGET_SECONDS = 5.0
TRACES_PATH = "/v1/traces"
DEPLOYMENT_ENVIRONMENT = "deployment.environment.name"
PROCESS_ROLE = "whisperer.role"


def build_tracer_provider(
    settings: ObservabilitySettings,
    environment: Environment,
    role: ProcessRole,
    metrics: ObservabilityMetrics,
) -> TracerProvider:
    """The provider of one process; the caller installs it and shuts it down at stop."""
    resource = Resource(
        {
            SERVICE_NAME: settings.otel_service_name,
            SERVICE_VERSION: version("whisperer"),
            DEPLOYMENT_ENVIRONMENT: environment.value,
            PROCESS_ROLE: role.value,
        }
    )
    # Без выхода при завершении интерпретатора: провайдер останавливает сам процесс.
    provider = TracerProvider(resource=resource, sampler=ALWAYS_ON, shutdown_on_exit=False)
    if settings.otel_exporter_otlp_endpoint is not None:
        exporter = OTLPSpanExporter(
            endpoint=traces_endpoint(settings.otel_exporter_otlp_endpoint),
            timeout=EXPORT_TIMEOUT_SECONDS,
        )
        provider.add_span_processor(BoundedSpanProcessor(exporter, metrics))
    return provider


def traces_endpoint(base: HttpUrl) -> str:
    """`http://collector:4318` → `http://collector:4318/v1/traces`, as the OTLP variable means."""
    return str(base).rstrip("/") + TRACES_PATH


class BoundedSpanProcessor(SpanProcessor):
    """A batch processor that admits at most `capacity` spans awaiting export.

    It counts spans from admission until the exporter takes them, so the batch queue
    behind it never overflows; a span over the bound is dropped and counted here.
    """

    def __init__(
        self,
        exporter: SpanExporter,
        metrics: ObservabilityMetrics,
        capacity: int = SPAN_QUEUE_CAPACITY,
    ) -> None:
        self._metrics = metrics
        self._capacity = capacity
        self._pending = 0
        self._lock = threading.Lock()
        self._exporter = _AccountingExporter(exporter, self, metrics)
        # Тип базового класса: у BatchSpanProcessor.shutdown нет аннотаций.
        self._batch: SpanProcessor = BatchSpanProcessor(
            self._exporter,
            max_queue_size=capacity,
            schedule_delay_millis=EXPORT_DELAY_MILLIS,
            max_export_batch_size=min(EXPORT_BATCH_SIZE, capacity),
        )

    def on_start(self, span: Span, parent_context: Context | None = None) -> None:
        """Nothing happens when a span starts."""

    def on_end(self, span: ReadableSpan) -> None:
        """Admit a finished sampled span for export, or drop it if the bound is reached."""
        if not (span.context and span.context.trace_flags.sampled):
            return
        with self._lock:
            admitted = self._pending < self._capacity
            if admitted:
                self._pending += 1
        if admitted:
            self._batch.on_end(span)
        else:
            self._metrics.count_dropped("traces", "queue_full")

    def release(self, count: int) -> None:
        """The exporter took `count` spans; they no longer occupy the bound."""
        with self._lock:
            self._pending -= count

    def shutdown(self) -> None:
        """Export what is queued within the shutdown budget, then stop; the rest is dropped."""
        self._exporter.stop_exporting_after(SHUTDOWN_BUDGET_SECONDS)
        self._batch.shutdown()

    def force_flush(self, timeout_millis: int = 30_000) -> bool:
        """Export everything queued now."""
        return self._batch.force_flush(timeout_millis)


class _AccountingExporter(SpanExporter):
    """Releases the bound, counts refused batches and drops batches after the deadline."""

    def __init__(
        self, exporter: SpanExporter, processor: BoundedSpanProcessor, metrics: ObservabilityMetrics
    ) -> None:
        self._exporter = exporter
        self._processor = processor
        self._metrics = metrics
        self._deadline: float | None = None

    def stop_exporting_after(self, seconds: float) -> None:
        self._deadline = time.monotonic() + seconds

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        self._processor.release(len(spans))
        if self._deadline is not None and time.monotonic() > self._deadline:
            self._metrics.count_dropped("traces", "shutdown", len(spans))
            return SpanExportResult.FAILURE
        result = SpanExportResult.FAILURE
        try:
            result = self._exporter.export(spans)
        finally:
            if result is not SpanExportResult.SUCCESS:
                self._metrics.count_dropped("traces", "export_failed", len(spans))
        return result

    def shutdown(self) -> None:
        self._exporter.shutdown()

    def force_flush(self, timeout_millis: int = 30_000) -> bool:
        return self._exporter.force_flush(timeout_millis)
