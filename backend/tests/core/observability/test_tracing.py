"""Spans leave through a bounded queue; what does not fit or fails is counted, never waited on."""

import threading
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from prometheus_client import CollectorRegistry
from pydantic import HttpUrl

from whisperer.core.config.roles import ProcessRole
from whisperer.core.config.sections import ObservabilitySettings
from whisperer.core.config.values import Environment
from whisperer.core.observability import tracing
from whisperer.core.observability.metrics import ObservabilityMetrics
from whisperer.core.observability.tracing import (
    BoundedSpanProcessor,
    build_tracer_provider,
    traces_endpoint,
)

WAIT_SECONDS = 5


class GatedExporter(SpanExporter):
    """Takes spans, reports when an export starts, and holds it until released."""

    def __init__(self, result: SpanExportResult = SpanExportResult.SUCCESS) -> None:
        self.result = result
        self.exported: list[ReadableSpan] = []
        self.started = threading.Event()
        self.release = threading.Event()
        self.release.set()

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        self.started.set()
        self.release.wait(WAIT_SECONDS)
        self.exported.extend(spans)
        return self.result


def dropped(registry: CollectorRegistry, reason: str) -> float:
    value = registry.get_sample_value(
        "whisperer_telemetry_dropped_total", {"signal": "traces", "reason": reason}
    )
    return value or 0.0


@contextmanager
def traced(
    exporter: SpanExporter, capacity: int
) -> Iterator[tuple[TracerProvider, CollectorRegistry]]:
    registry = CollectorRegistry()
    provider = TracerProvider(shutdown_on_exit=False)
    provider.add_span_processor(
        BoundedSpanProcessor(exporter, ObservabilityMetrics(registry), capacity=capacity)
    )
    try:
        yield provider, registry
    finally:
        provider.shutdown()


def end_spans(provider: TracerProvider, count: int) -> None:
    tracer = provider.get_tracer("tests")
    for number in range(count):
        tracer.start_span(f"span-{number}").end()


def test_spans_over_the_bound_are_dropped_and_counted() -> None:
    exporter = GatedExporter()
    exporter.release.clear()
    with traced(exporter, capacity=4) as (provider, registry):
        end_spans(provider, 4)
        assert exporter.started.wait(WAIT_SECONDS)
        end_spans(provider, 6)

        assert dropped(registry, "queue_full") == 2
        exporter.release.set()
        provider.force_flush()

    assert len(exporter.exported) == 8


def test_a_refused_batch_is_counted() -> None:
    exporter = GatedExporter(SpanExportResult.FAILURE)
    with traced(exporter, capacity=16) as (provider, registry):
        end_spans(provider, 3)
        provider.force_flush()

        assert dropped(registry, "export_failed") == 3


def test_spans_left_after_the_shutdown_budget_are_counted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(tracing, "SHUTDOWN_BUDGET_SECONDS", 0.0)
    exporter = GatedExporter()
    with traced(exporter, capacity=16) as (provider, registry):
        end_spans(provider, 3)
        provider.shutdown()

        assert dropped(registry, "shutdown") == 3
        assert exporter.exported == []


@pytest.mark.parametrize("base", ["http://collector:4318", "http://collector:4318/"])
def test_the_traces_path_is_added_to_the_collector_address(base: str) -> None:
    assert traces_endpoint(HttpUrl(base)) == "http://collector:4318/v1/traces"


def test_the_provider_describes_the_process() -> None:
    provider = build_tracer_provider(
        ObservabilitySettings(otel_service_name="whisperer-staging"),
        Environment.STAGING,
        ProcessRole.SCHEDULER,
        ObservabilityMetrics(CollectorRegistry()),
    )

    attributes = provider.resource.attributes
    assert attributes["service.name"] == "whisperer-staging"
    assert attributes["deployment.environment.name"] == "staging"
    assert attributes["whisperer.role"] == "scheduler"
    assert attributes["service.version"]


class CollectorStub(BaseHTTPRequestHandler):
    """Accepts OTLP/HTTP posts and remembers their paths and content types."""

    received: list[tuple[str, str]]

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        self.received.append((self.path, self.headers.get("Content-Type", "")))
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        """Silence the default request log on stderr."""


def test_spans_reach_the_configured_collector() -> None:
    received: list[tuple[str, str]] = []

    class Handler(CollectorStub):
        pass

    Handler.received = received
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    serving = threading.Thread(target=server.serve_forever, daemon=True)
    serving.start()
    endpoint = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        provider = build_tracer_provider(
            ObservabilitySettings(otel_exporter_otlp_endpoint=HttpUrl(endpoint)),
            Environment.DEVELOPMENT,
            ProcessRole.API,
            ObservabilityMetrics(CollectorRegistry()),
        )
        end_spans(provider, 2)
        provider.force_flush()
        provider.shutdown()
    finally:
        server.shutdown()
        server.server_close()

    assert received == [("/v1/traces", "application/x-protobuf")]
