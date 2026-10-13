"""HTTP metric labels: closed values, bounded series, no second route match."""

import sys
from types import FrameType

import pytest
from fastapi import FastAPI
from fastapi.routing import iter_route_contexts
from hypothesis import given, settings
from hypothesis import strategies as st
from starlette.types import ASGIApp

from shosai.core.web.health import build_health_router
from shosai.core.web.http_metrics import ABSENT, KNOWN_METHODS, OTHER, status_labels
from tests.core.web.asgi import asgi_scope, call
from tests.core.web.metric_samples import requests_counted
from tests.core.web.probe_app import build_probe_app, probe_router

# Коды, которые оболочка и пробное приложение способны ответить на любой запрос.
SHELL_STATUSES = {"200", "307", "404", "405", "422", "429", "500", "503"}

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
    [(seen_method, seen_route, seen_status, seen_scheme, seen_error)] = requests_counted(
        probe.registry
    )
    assert seen_route in served | {ABSENT}
    assert seen_method in KNOWN_METHODS | {OTHER}
    assert seen_status in SHELL_STATUSES
    assert seen_scheme == "http"
    assert seen_error in {ABSENT, seen_status}


async def test_distinct_paths_do_not_grow_the_series() -> None:
    probe = build_probe_app()
    for index in range(300):
        for method in ("GET", "BREW", "PATCH"):
            await call(probe.app, asgi_scope(method, f"/v1/probe/items/user-{index}@example.com/"))
            await call(probe.app, asgi_scope(method, f"/v1/nothing/{index}"))

    assert len(requests_counted(probe.registry)) <= 3 * 2


@pytest.mark.parametrize(
    ("status", "labels"),
    [
        (200, ("200", ABSENT)),
        (304, ("304", ABSENT)),
        (499, ("499", ABSENT)),
        (503, ("503", "503")),
        (99, ("500", "500")),
        (999, ("500", "500")),
        (None, (ABSENT, OTHER)),
    ],
)
def test_a_status_gives_a_code_and_an_error_type(
    status: int | None, labels: tuple[str, str]
) -> None:
    assert status_labels(status) == labels


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
