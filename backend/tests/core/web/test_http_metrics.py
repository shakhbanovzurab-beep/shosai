"""HTTP metrics keep the instrumentator's contract and count each request exactly once."""

import asyncio

import pytest
from fastapi import APIRouter
from starlette.types import Message

from tests.core.observability.capture import captured_logs
from tests.core.web.asgi import asgi_scope, call
from tests.core.web.metric_samples import requests_total, samples
from tests.core.web.probe_app import ITEM_ROUTE, build_probe_app, client_of
from whisperer.core.config.sections import WebSettings
from whisperer.core.web.http_metrics import OTHER_METHOD, UNMATCHED_HANDLER

# Контракт prometheus-fastapi-instrumentator 8.1.0, metrics.default() (ADR 0012): на нём
# стоят дашборды и алерты, поэтому он зафиксирован здесь дословно.
CONTRACT = {
    "http_requests": ("counter", "Total number of requests by method, status and handler."),
    "http_request_size_bytes": (
        "summary",
        "Content length of incoming requests by handler. Only value of header is respected. "
        "Otherwise ignored. No percentile calculated. ",
    ),
    "http_response_size_bytes": (
        "summary",
        "Content length of outgoing responses by handler. Only value of header is respected. "
        "Otherwise ignored. No percentile calculated. ",
    ),
    "http_request_duration_highr_seconds": (
        "histogram",
        "Latency with many buckets but no API specific labels. "
        "Made for more accurate percentile calculations. ",
    ),
    "http_request_duration_seconds": (
        "histogram",
        "Latency with only few buckets by handler. "
        "Made to be only used if aggregation by handler is important. ",
    ),
}
LABELS = {
    "http_requests_total": {"method", "status", "handler"},
    "http_request_size_bytes_count": {"handler"},
    "http_request_size_bytes_sum": {"handler"},
    "http_response_size_bytes_count": {"handler"},
    "http_response_size_bytes_sum": {"handler"},
    "http_request_duration_highr_seconds_bucket": {"le"},
    "http_request_duration_highr_seconds_count": set(),
    "http_request_duration_highr_seconds_sum": set(),
    "http_request_duration_seconds_bucket": {"method", "handler", "le"},
    "http_request_duration_seconds_count": {"method", "handler"},
    "http_request_duration_seconds_sum": {"method", "handler"},
}
HIGHR = ["0.01", "0.025", "0.05", "0.075", "0.1", "0.25", "0.5", "0.75", "1.0", "1.5",
         "2.0", "2.5", "3.0", "3.5", "4.0", "4.5", "5.0", "7.5", "10.0", "30.0", "60.0",
         "+Inf"]  # fmt: skip
LOWR = ["0.1", "0.5", "1.0", "+Inf"]


async def test_the_five_metrics_keep_the_instrumentator_contract() -> None:
    probe = build_probe_app()
    async with client_of(probe.app) as client:
        await client.get("/v1/probe/items/1")

    families = {f.name: f for f in probe.registry.collect() if f.name.startswith("http_")}
    assert {name: (f.type, f.documentation) for name, f in families.items()} == CONTRACT
    names = {name: set(labels) for name, labels, _ in samples(probe.registry)}
    assert names == LABELS
    buckets = [(n, labels["le"]) for n, labels, _ in samples(probe.registry) if "le" in labels]
    assert [le for n, le in buckets if n.startswith("http_request_duration_highr")] == HIGHR
    assert [le for n, le in buckets if n == "http_request_duration_seconds_bucket"] == LOWR


OUTCOMES = [
    ("GET", "/v1/probe/items/1", ("GET", "2xx", ITEM_ROUTE)),
    ("GET", "/v1/probe/items/1/", ("GET", "3xx", UNMATCHED_HANDLER)),
    ("GET", "/v1/missing", ("GET", "4xx", UNMATCHED_HANDLER)),
    ("DELETE", "/v1/probe/items/1", ("DELETE", "4xx", ITEM_ROUTE)),
    ("GET", "/v1/probe/items/abc", ("GET", "4xx", ITEM_ROUTE)),
    ("GET", "/v1/probe/rate-limited", ("GET", "4xx", "/v1/probe/rate-limited")),
    ("GET", "/v1/probe/unavailable", ("GET", "5xx", "/v1/probe/unavailable")),
    ("GET", "/v1/probe/crash", ("GET", "5xx", "/v1/probe/crash")),
    ("FOOBAR", "/v1/health", (OTHER_METHOD, "4xx", "/v1/health")),
    ("get", "/v1/health", (OTHER_METHOD, "4xx", "/v1/health")),
    ("", "/v1/health", (OTHER_METHOD, "4xx", "/v1/health")),
]


@pytest.mark.parametrize(("method", "path", "labels"), OUTCOMES)
async def test_each_outcome_is_counted_once_under_closed_labels(
    method: str, path: str, labels: tuple[str, str, str]
) -> None:
    probe = build_probe_app()
    await call(probe.app, asgi_scope(method, path))

    assert requests_total(probe.registry) == {labels: 1}


async def test_a_failure_after_the_status_was_sent_counts_that_status() -> None:
    router = APIRouter(prefix="/v1/stream")

    @router.get("/broken")
    async def broken() -> None:
        """Answers, then fails while the boundary still holds the request."""

    probe = build_probe_app(extra=[router])

    async def fail_after_start(message: Message) -> None:
        if message["type"] == "http.response.body":
            message_text = "клиент ушёл"
            raise ConnectionResetError(message_text)

    await call(probe.app, asgi_scope("GET", "/v1/stream/broken"), send=fail_after_start)

    assert requests_total(probe.registry) == {("GET", "2xx", "/v1/stream/broken"): 1}


async def test_a_cancelled_request_is_counted_once_as_a_server_error() -> None:
    started = asyncio.Event()
    router = APIRouter(prefix="/v1/slow")

    @router.get("/{job_id}")
    async def slow(job_id: str) -> dict[str, str]:
        """Waits until the server cancels the request."""
        started.set()
        await asyncio.Event().wait()
        return {"id": job_id}

    probe = build_probe_app(extra=[router])
    task = asyncio.create_task(call(probe.app, asgi_scope("GET", "/v1/slow/7")))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert requests_total(probe.registry) == {("GET", "5xx", "/v1/slow/{job_id}"): 1}


async def test_a_client_gone_before_its_body_is_counted_once() -> None:
    probe = build_probe_app()

    async def disconnected() -> Message:
        return {"type": "http.disconnect"}

    scope = asgi_scope("POST", "/v1/probe/credentials", headers=[(b"content-length", b"40")])
    await call(probe.app, scope, receive=disconnected)

    assert sum(requests_total(probe.registry).values()) == 1


@pytest.mark.parametrize(
    ("header", "observed"),
    [
        (None, 0.0),
        (b"12", 12.0),
        (b" 7 ", 7.0),
        (b"abc", 0.0),
        (b"-5", 0.0),
        (b"", 0.0),
        (b"\xb9", 0.0),
        ("\u0663".encode(), 0.0),
    ],
)
async def test_the_request_size_is_the_header_or_zero_and_never_fails(
    header: bytes | None, observed: float
) -> None:
    probe = build_probe_app()
    headers = [] if header is None else [(b"content-length", header)]
    await call(probe.app, asgi_scope("GET", "/v1/health", headers=headers))

    size = probe.registry.get_sample_value("http_request_size_bytes_sum", {"handler": "/v1/health"})
    assert size == observed


async def test_the_last_resort_500_counts_the_size_it_sent() -> None:
    probe = build_probe_app()
    async with client_of(probe.app) as client:
        response = await client.get("/v1/probe/crash")

    labels = {"handler": "/v1/probe/crash"}
    assert probe.registry.get_sample_value("http_response_size_bytes_sum", labels) == len(
        response.content
    )


async def test_every_request_of_a_mixed_run_is_counted_exactly_once() -> None:
    probe = build_probe_app(
        WebSettings.model_validate({"cors_allowed_origins": "https://a.example"})
    )
    preflight = [(b"origin", b"https://a.example"), (b"access-control-request-method", b"GET")]
    runs = [asgi_scope(method, path) for method, path, _ in OUTCOMES]
    runs.append(asgi_scope("OPTIONS", "/v1/health", headers=preflight))
    for scope in runs:
        await call(probe.app, scope)

    total = sum(requests_total(probe.registry).values())
    highr = probe.registry.get_sample_value("http_request_duration_highr_seconds_count")
    assert total == highr == len(runs)
    assert requests_total(probe.registry)[("OPTIONS", "2xx", UNMATCHED_HANDLER)] == 1


async def test_the_access_line_names_the_same_route_as_the_metric() -> None:
    probe = build_probe_app()
    with captured_logs() as captured:
        for method, path, _ in OUTCOMES[:8]:
            await call(probe.app, asgi_scope(method, path))

    logged = {line["route"] for line in captured.lines() if "route" in line}
    counted = {handler for _, _, handler in requests_total(probe.registry)}
    assert {route if route != "unmatched" else UNMATCHED_HANDLER for route in logged} == counted
