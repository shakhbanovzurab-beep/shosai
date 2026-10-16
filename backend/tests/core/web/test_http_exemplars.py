"""Exemplars of the HTTP metric lead only to traces the collector always keeps (F5 plan §3.6)."""

import pytest
from prometheus_client import CollectorRegistry
from prometheus_client.exposition import choose_encoder

from shosai.core.web.http_metrics import (
    DURATION_METRIC,
    SLOW_REQUEST_SECONDS,
    CompletedRequest,
    exemplar_of,
)
from tests.core.web.probe_app import build_probe_app, client_of

TRACE_ID = "4bf92f3577b34da6a3ce929d0e0e4736"
OPENMETRICS = "application/openmetrics-text; version=1.0.0"


def completed(duration: float, trace_id: str | None = TRACE_ID) -> CompletedRequest:
    return CompletedRequest("GET", "/v1/x", 200, "https", duration, trace_id)


@pytest.mark.parametrize(
    ("request_", "failed", "expected"),
    [
        (completed(0.01), False, None),
        (completed(SLOW_REQUEST_SECONDS), False, None),
        (completed(SLOW_REQUEST_SECONDS + 0.001), False, {"trace_id": TRACE_ID}),
        (completed(0.01), True, {"trace_id": TRACE_ID}),
        (completed(5.0, trace_id=None), True, None),
    ],
    ids=["fast", "at-threshold", "slow", "failed", "no-span"],
)
def test_only_failed_or_slow_requests_carry_their_trace(
    request_: CompletedRequest, *, failed: bool, expected: dict[str, str] | None
) -> None:
    assert exemplar_of(request_, failed=failed) == expected


def bucket_exemplars(registry: CollectorRegistry) -> list[dict[str, str]]:
    return [
        dict(sample.exemplar.labels)
        for family in registry.collect()
        if family.name == DURATION_METRIC
        for sample in family.samples
        if sample.name.endswith("_bucket") and sample.exemplar is not None
    ]


async def test_a_server_error_carries_the_trace_of_its_server_span() -> None:
    probe = build_probe_app()
    async with client_of(probe.app) as client:
        await client.get("/v1/probe/items/1")
        await client.get("/v1/probe/crash")

    [span] = [span for span in probe.finished_spans() if "crash" in span.name]
    trace_id = format(span.context.trace_id, "032x")
    assert bucket_exemplars(probe.registry) == [{"trace_id": trace_id}]
    # Как отдаёт /metrics служебного порта, когда Prometheus просит OpenMetrics (core/web/ops.py).
    encoder, _ = choose_encoder(OPENMETRICS)
    assert f'# {{trace_id="{trace_id}"}}' in encoder(probe.registry).decode()
