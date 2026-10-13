"""The HTTP metric keeps the semantic conventions and counts each request exactly once."""

import asyncio

import pytest
from fastapi import APIRouter
from starlette.types import Message

from shosai.core.config.sections import WebSettings
from shosai.core.web.http_metrics import ABSENT, OTHER
from tests.core.observability.capture import captured_logs
from tests.core.web.asgi import asgi_scope, call
from tests.core.web.metric_samples import requests_counted, samples
from tests.core.web.probe_app import ITEM_ROUTE, build_probe_app, client_of

# Семантические соглашения OpenTelemetry для HTTP-сервера в именах экспортёра Prometheus
# (ADR 0012 с поправкой OD-3): на них стоят дашборды и алерты, поэтому контракт здесь.
CONTRACT = {
    "http_server_request_duration_seconds": ("histogram", "Duration of HTTP server requests.")
}
REQUEST_LABELS = {
    "http_request_method",
    "http_route",
    "http_response_status_code",
    "url_scheme",
    "error_type",
}
LABELS = {
    "http_server_request_duration_seconds_bucket": REQUEST_LABELS | {"le"},
    "http_server_request_duration_seconds_count": REQUEST_LABELS,
    "http_server_request_duration_seconds_sum": REQUEST_LABELS,
}
BUCKETS = ["0.005", "0.01", "0.025", "0.05", "0.075", "0.1", "0.25", "0.5", "0.75", "1.0",
           "2.5", "5.0", "7.5", "10.0", "+Inf"]  # fmt: skip


async def test_the_duration_histogram_keeps_the_semantic_conventions() -> None:
    probe = build_probe_app()
    async with client_of(probe.app) as client:
        await client.get("/v1/probe/items/1")

    families = {f.name: f for f in probe.registry.collect() if f.name.startswith("http_")}
    assert {name: (f.type, f.documentation) for name, f in families.items()} == CONTRACT
    names = {name: set(labels) for name, labels, _ in samples(probe.registry)}
    assert names == LABELS
    assert [labels["le"] for _, labels, _ in samples(probe.registry) if "le" in labels] == BUCKETS


OUTCOMES = [
    ("GET", "/v1/probe/items/1", ("GET", ITEM_ROUTE, "200", "http", ABSENT)),
    ("GET", "/v1/probe/items/1/", ("GET", ABSENT, "307", "http", ABSENT)),
    ("GET", "/v1/missing", ("GET", ABSENT, "404", "http", ABSENT)),
    ("DELETE", "/v1/probe/items/1", ("DELETE", ITEM_ROUTE, "405", "http", ABSENT)),
    ("GET", "/v1/probe/items/abc", ("GET", ITEM_ROUTE, "422", "http", ABSENT)),
    ("GET", "/v1/probe/rate-limited", ("GET", "/v1/probe/rate-limited", "429", "http", ABSENT)),
    ("GET", "/v1/probe/unavailable", ("GET", "/v1/probe/unavailable", "503", "http", "503")),
    ("GET", "/v1/probe/crash", ("GET", "/v1/probe/crash", "500", "http", "500")),
    ("FOOBAR", "/v1/health", (OTHER, "/v1/health", "405", "http", ABSENT)),
    ("get", "/v1/health", (OTHER, "/v1/health", "405", "http", ABSENT)),
    ("", "/v1/health", (OTHER, "/v1/health", "405", "http", ABSENT)),
]


@pytest.mark.parametrize(("method", "path", "labels"), OUTCOMES)
async def test_each_outcome_is_counted_once_under_closed_labels(
    method: str, path: str, labels: tuple[str, str, str, str, str]
) -> None:
    probe = build_probe_app()
    await call(probe.app, asgi_scope(method, path))

    assert requests_counted(probe.registry) == {labels: 1}


async def test_the_scheme_is_https_or_http_whatever_the_scope_says() -> None:
    probe = build_probe_app()
    for scheme in ("https", "HTTPS", "gopher"):
        await call(probe.app, asgi_scope("GET", "/v1/health") | {"scheme": scheme})

    assert {labels[3]: count for labels, count in requests_counted(probe.registry).items()} == {
        "https": 1,
        "http": 2,
    }


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

    assert requests_counted(probe.registry) == {
        ("GET", "/v1/stream/broken", "200", "http", ABSENT): 1
    }


async def test_a_cancelled_request_is_counted_once_as_an_error_without_a_status() -> None:
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

    assert requests_counted(probe.registry) == {
        ("GET", "/v1/slow/{job_id}", ABSENT, "http", OTHER): 1
    }


async def test_a_client_gone_before_its_body_is_counted_once() -> None:
    probe = build_probe_app()

    async def disconnected() -> Message:
        return {"type": "http.disconnect"}

    scope = asgi_scope("POST", "/v1/probe/credentials", headers=[(b"content-length", b"40")])
    await call(probe.app, scope, receive=disconnected)

    assert sum(requests_counted(probe.registry).values()) == 1


async def test_every_request_of_a_mixed_run_is_counted_exactly_once() -> None:
    probe = build_probe_app(
        WebSettings.model_validate({"cors_allowed_origins": "https://a.example"})
    )
    preflight = [(b"origin", b"https://a.example"), (b"access-control-request-method", b"GET")]
    runs = [asgi_scope(method, path) for method, path, _ in OUTCOMES]
    runs.append(asgi_scope("OPTIONS", "/v1/health", headers=preflight))
    for scope in runs:
        await call(probe.app, scope)

    counted = requests_counted(probe.registry)
    assert sum(counted.values()) == len(runs)
    assert counted["OPTIONS", ABSENT, "200", "http", ABSENT] == 1


async def test_the_access_line_names_the_same_route_as_the_metric() -> None:
    probe = build_probe_app()
    with captured_logs() as captured:
        for method, path, _ in OUTCOMES[:8]:
            await call(probe.app, asgi_scope(method, path))

    logged = {line["route"] for line in captured.lines() if "route" in line}
    counted = {route for _, route, _, _, _ in requests_counted(probe.registry)}
    assert {route if route != "unmatched" else ABSENT for route in logged} == counted
