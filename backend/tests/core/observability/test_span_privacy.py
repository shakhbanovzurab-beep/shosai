"""Attributes that may carry user input never reach a span."""

from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.sampling import Decision
from prometheus_client import CollectorRegistry

from shosai.core.config.roles import ProcessRole
from shosai.core.config.sections import ObservabilitySettings
from shosai.core.config.values import Environment
from shosai.core.observability.metrics import ObservabilityMetrics
from shosai.core.observability.span_privacy import (
    PRIVATE_SPAN_ATTRIBUTES,
    PrivateAttributesSampler,
)
from shosai.core.observability.tracing import build_tracer_provider

START_ATTRIBUTES = {
    "http.request.method": "GET",
    "url.path": "/s/share-token-123",
    "url.query": "q=someone@example.com",
    "url.full": "https://shosai.tech/s/share-token-123",
    "client.address": "203.0.113.9",
}


def test_every_span_is_recorded_without_the_private_attributes() -> None:
    result = PrivateAttributesSampler().should_sample(None, 1, "GET", attributes=START_ATTRIBUTES)

    assert result.decision is Decision.RECORD_AND_SAMPLE
    assert dict(result.attributes) == {"http.request.method": "GET"}


def test_the_process_provider_drops_them_from_its_spans() -> None:
    provider = build_tracer_provider(
        ObservabilitySettings(),
        Environment.DEVELOPMENT,
        ProcessRole.API,
        ObservabilityMetrics(CollectorRegistry()),
    )
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    with provider.get_tracer("tests").start_as_current_span("GET", attributes=START_ATTRIBUTES):
        pass
    [span] = exporter.get_finished_spans()
    attributes = dict(span.attributes or {})

    assert attributes == {"http.request.method": "GET"}
    assert not PRIVATE_SPAN_ATTRIBUTES & set(attributes)
    assert "PrivateAttributesSampler" in provider.sampler.get_description()
