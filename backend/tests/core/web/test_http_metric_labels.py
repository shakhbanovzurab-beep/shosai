"""HTTP metric labels: closed values, bounded series, no second route match."""

import sys
from types import FrameType

import pytest
from fastapi import FastAPI
from fastapi.routing import iter_route_contexts
from hypothesis import given, settings
from hypothesis import strategies as st
from starlette.types import ASGIApp

from tests.core.web.asgi import asgi_scope, call
from tests.core.web.metric_samples import requests_total
from tests.core.web.probe_app import build_probe_app, probe_router
from whisperer.core.web.health import build_health_router
from whisperer.core.web.http_metrics import (
    KNOWN_METHODS,
    OTHER_METHOD,
    UNMATCHED_HANDLER,
    content_length,
    status_class,
)

STATUS_CLASSES = {"1xx", "2xx", "3xx", "4xx", "5xx"}

PATHS = st.text(st.characters(codec="utf-8", exclude_categories=("Cs", "Cc")), max_size=60)


@settings(max_examples=200, deadline=None)
@given(
    path=PATHS.map(lambda text: "/" + text),
    method=st.one_of(
        st.sampled_from(sorted(KNOWN_METHODS)), st.from_regex(r"[A-Za-z-]{0,40}", fullmatch=True)
    ),
    query=PATHS,
    length=st.binary(max_size=12),
)
async def test_no_label_value_ever_comes_from_the_request(
    path: str, method: str, query: str, length: bytes
) -> None:
    probe = build_probe_app()
    scope = asgi_scope(method, path, query=query, headers=[(b"content-length", length)])
    await call(probe.app, scope)

    served = {context.path for context in iter_route_contexts(probe.app.routes)}
    [(seen_method, seen_status, seen_handler)] = requests_total(probe.registry)
    assert seen_handler in served | {UNMATCHED_HANDLER}
    assert seen_method in KNOWN_METHODS | {OTHER_METHOD}
    assert seen_status in STATUS_CLASSES


async def test_distinct_paths_do_not_grow_the_series() -> None:
    probe = build_probe_app()
    for index in range(300):
        for method in ("GET", "BREW", "PATCH"):
            await call(probe.app, asgi_scope(method, f"/v1/probe/items/user-{index}@example.com/"))
            await call(probe.app, asgi_scope(method, f"/v1/nothing/{index}"))

    assert len(requests_total(probe.registry)) <= 3 * 2


@pytest.mark.parametrize(
    ("status", "label"),
    [(200, "2xx"), (304, "3xx"), (499, "4xx"), (599, "5xx"), (99, "5xx"), (999, "5xx")],
)
def test_a_status_maps_to_one_of_five_classes(status: int, label: str) -> None:
    assert status_class(status) == label


def test_content_length_reads_only_a_decimal_header() -> None:
    assert content_length([(b"Content-Length", b"42"), (b"content-length", b"1")]) == 42
    assert content_length([(b"host", b"t")]) == 0
    assert content_length([(b"content-length", b"4" * 30)]) == int("4" * 30)


@pytest.mark.parametrize("path", ["/v1/health", "/v1/probe/items/7", "/v1/none/x/"])
async def test_the_shell_adds_no_route_matching_to_fastapi_routing(path: str) -> None:
    # Та же таблица маршрутов, что у оболочки, но без её middleware.
    routing_only = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)
    routing_only.include_router(build_health_router())
    routing_only.include_router(probe_router())

    shell = await matches_during(build_probe_app().app, path)

    assert shell == await matches_during(routing_only, path)


async def matches_during(app: ASGIApp, path: str) -> int:
    """How many route `matches` calls one request causes, after a warm-up request."""
    await call(app, asgi_scope("GET", path))
    calls = 0

    def count(frame: FrameType, event: str, _arg: object) -> None:
        nonlocal calls
        if event == "call" and frame.f_code.co_name == "matches":
            calls += 1

    sys.setprofile(count)
    try:
        await call(app, asgi_scope("GET", path))
    finally:
        sys.setprofile(None)
    return calls
