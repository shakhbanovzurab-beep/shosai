"""The request boundary: ids, common headers, one access line, the last-resort 500."""

from typing import Any

import pytest
import structlog
from fastapi import FastAPI
from prometheus_client import CollectorRegistry
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from shosai.core.web.boundary import RequestBoundary
from shosai.core.web.http_metrics import HttpMetrics
from shosai.core.web.request_ids import (
    REQUEST_ID_HEADER,
    RequestIdMissingError,
    request_id_of,
)
from shosai.core.web.route_templates import RouteTemplates
from tests.core.observability.capture import captured_logs
from tests.core.web.probe_app import ITEM_ROUTE, build_probe_app, client_of

log = structlog.stdlib.get_logger("tests.boundary")


def boundary(app: ASGIApp) -> RequestBoundary:
    """The boundary around a bare ASGI app, with its own metrics and no routes."""
    templates = RouteTemplates(FastAPI(openapi_url=None, docs_url=None, redoc_url=None))
    return RequestBoundary(app, metrics=HttpMetrics(CollectorRegistry()), templates=templates)


async def test_a_safe_client_request_id_is_kept() -> None:
    async with client_of(build_probe_app().app) as client:
        response = await client.get("/v1/health", headers={REQUEST_ID_HEADER: "web-1.a_b"})

    assert response.headers[REQUEST_ID_HEADER] == "web-1.a_b"


@pytest.mark.parametrize("incoming", ["a b", "x" * 65, "line\nbreak", "", "id;drop"])
async def test_an_unsafe_client_request_id_is_replaced_by_a_new_one(incoming: str) -> None:
    async with client_of(build_probe_app().app) as client:
        response = await client.get("/v1/health", headers={REQUEST_ID_HEADER: incoming})

    request_id = response.headers[REQUEST_ID_HEADER]
    assert request_id != incoming
    assert len(request_id) == 32
    int(request_id, 16)


async def test_each_request_gets_its_own_id() -> None:
    async with client_of(build_probe_app().app) as client:
        first = await client.get("/v1/health")
        second = await client.get("/v1/health")

    assert first.headers[REQUEST_ID_HEADER] != second.headers[REQUEST_ID_HEADER]


async def test_one_access_line_names_the_route_template_and_never_the_path() -> None:
    with captured_logs() as captured:
        async with client_of(build_probe_app().app) as client:
            response = await client.get("/v1/probe/items/42?q=private-search")

    handler_line, access_line = captured.lines()
    request_id = response.headers[REQUEST_ID_HEADER]
    assert handler_line["request_id"] == request_id
    assert access_line["message"] == "Запрос обработан"
    assert access_line["level"] == "info"
    assert access_line["request_id"] == request_id
    assert access_line["method"] == "GET"
    assert access_line["route"] == ITEM_ROUTE
    assert access_line["status"] == 200
    assert access_line["duration_ms"] >= 0
    assert "42" not in access_line["route"]
    assert "private-search" not in captured.text()


async def test_an_unmatched_path_is_logged_without_the_path() -> None:
    with captured_logs() as captured:
        async with client_of(build_probe_app().app) as client:
            await client.get("/v1/users/someone@example.com")

    [line] = captured.lines()
    assert line["route"] == "unmatched"
    assert line["status"] == 404
    assert "someone" not in captured.text()


async def test_a_handled_server_error_is_a_warning_without_a_stack() -> None:
    with captured_logs() as captured:
        async with client_of(build_probe_app().app) as client:
            await client.get("/v1/probe/unavailable")

    [line] = captured.lines()
    assert line["level"] == "warning"
    assert line["status"] == 503
    assert "exception" not in line


@pytest.mark.parametrize("path", ["/v1/health", "/v1/probe/crash", "/v1/nothing"])
async def test_every_response_has_the_security_headers_and_https_adds_hsts(path: str) -> None:
    app = build_probe_app().app
    async with client_of(app) as client:
        plain = await client.get(path)
    async with client_of(app, base_url="https://testserver") as client:
        secure = await client.get(path)

    for response in (plain, secure):
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "Strict-Transport-Security" not in plain.headers
    assert secure.headers["Strict-Transport-Security"] == "max-age=31536000"


class Recorder:
    """An ASGI `send` that keeps the messages, and a `receive` with an empty request."""

    def __init__(self) -> None:
        self.messages: list[Message] = []

    async def send(self, message: Message) -> None:
        """Keep the message."""
        self.messages.append(message)

    async def receive(self) -> Message:
        """The request has no body."""
        return {"type": "http.request", "body": b"", "more_body": False}


def http_scope() -> dict[str, Any]:
    """A minimal HTTP scope of a GET request."""
    return {"type": "http", "method": "GET", "path": "/v1/stream", "headers": []}


async def test_a_failure_after_the_status_was_sent_is_logged_once_and_not_raised() -> None:
    async def streams_then_fails(_scope: Scope, _receive: Receive, send: Send) -> None:
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"part", "more_body": True})
        message = "поток оборвался"
        raise RuntimeError(message)

    recorder = Recorder()
    with captured_logs() as captured:
        await boundary(streams_then_fails)(http_scope(), recorder.receive, recorder.send)

    assert [message["type"] for message in recorder.messages] == [
        "http.response.start",
        "http.response.body",
    ]
    [line] = captured.lines()
    assert line["message"] == "Ответ оборван ошибкой"
    assert line["status"] == 200
    assert "RuntimeError" in line["exception"]


async def test_an_app_that_never_answers_is_logged_as_an_error() -> None:
    async def silent(_scope: Scope, _receive: Receive, _send: Send) -> None:
        return

    recorder = Recorder()
    with captured_logs() as captured:
        await boundary(silent)(http_scope(), recorder.receive, recorder.send)

    [line] = captured.lines()
    assert line["level"] == "error"
    assert line["status"] is None


async def test_a_websocket_runs_inside_the_context_of_its_id() -> None:
    seen: list[str] = []

    async def socket(scope: Scope, _receive: Receive, _send: Send) -> None:
        seen.append(request_id_of(scope))
        log.info("Соединение открыто")

    recorder = Recorder()
    with captured_logs() as captured:
        scope = {"type": "websocket", "path": "/v1/ws/user", "headers": []}
        await boundary(socket)(scope, recorder.receive, recorder.send)

    [line] = captured.lines()
    assert line["request_id"] == seen[0]


async def test_other_scopes_pass_through_untouched() -> None:
    passed: list[Scope] = []

    async def lifespan(scope: Scope, _receive: Receive, _send: Send) -> None:
        passed.append(scope)

    recorder = Recorder()
    scope: dict[str, Any] = {"type": "lifespan"}
    await boundary(lifespan)(scope, recorder.receive, recorder.send)

    assert passed == [{"type": "lifespan"}]


def test_a_scope_that_did_not_pass_the_boundary_has_no_request_id() -> None:
    with pytest.raises(RequestIdMissingError):
        request_id_of({"type": "http"})
