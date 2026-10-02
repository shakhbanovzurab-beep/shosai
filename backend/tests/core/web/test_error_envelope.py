"""Every error path answers with the one envelope and the request id (ADR 0008)."""

from collections.abc import Awaitable, Callable
from typing import Any

import httpx
import pytest
from starlette.requests import Request
from starlette.responses import Response

from tests.core.observability.capture import captured_logs
from tests.core.web.probe_app import SECRET, build_probe_app, client_of
from whisperer.core.web.error_handlers import (
    render_app_error,
    render_http_exception,
    render_validation_error,
)
from whisperer.core.web.request_ids import REQUEST_ID_HEADER

ERROR_PATHS = [
    ("GET", "/v1/probe/domain-error", 409),
    ("GET", "/v1/probe/native-detail", 402),
    ("GET", "/v1/probe/rate-limited", 429),
    ("GET", "/v1/probe/http-code", 401),
    ("GET", "/v1/probe/http-sentence", 403),
    ("GET", "/v1/probe/under-yield-dependency", 422),
    ("POST", "/v1/probe/credentials", 422),
    ("GET", "/v1/probe/crash", 500),
    ("GET", "/v1/unknown/path", 404),
    ("DELETE", "/v1/health", 405),
]


async def call(method: str, path: str, json: object = None) -> httpx.Response:
    """One request to a fresh probe app."""
    async with client_of(build_probe_app().app) as client:
        return await client.request(method, path, json=json)


def envelope(response: httpx.Response) -> dict[str, Any]:
    """The JSON body, checked to be the envelope with the response's request id."""
    assert response.headers["content-type"] == "application/json"
    body: dict[str, Any] = response.json()
    assert set(body) == {"error", "detail"}
    assert body["error"]["request_id"] == response.headers[REQUEST_ID_HEADER]
    return body


@pytest.mark.parametrize(("method", "path", "status"), ERROR_PATHS)
async def test_every_error_path_answers_with_the_envelope(
    method: str, path: str, status: int
) -> None:
    response = await call(method, path, json={})

    assert response.status_code == status
    body = envelope(response)
    assert SECRET not in response.text
    assert "message" not in body["error"]


async def test_a_domain_error_carries_its_code_and_params() -> None:
    body = envelope(await call("GET", "/v1/probe/domain-error"))

    assert body == {
        "error": {
            "code": "item_locked",
            "request_id": body["error"]["request_id"],
            "params": {"item_id": 7, "until": "x1"},
        },
        "detail": "item_locked",
    }


async def test_a_native_route_keeps_the_draft_shape_of_detail() -> None:
    body = envelope(await call("GET", "/v1/probe/native-detail"))

    assert body["error"]["code"] == "quota_exceeded"
    assert body["detail"] == {"code": "quota"}


async def test_a_rate_limit_tells_when_to_retry() -> None:
    response = await call("GET", "/v1/probe/rate-limited")

    assert response.headers["Retry-After"] == "3"
    assert envelope(response)["error"]["params"] == {"retry_after_seconds": 2.2}


async def test_a_code_in_an_http_exception_becomes_the_code_and_its_headers_stay() -> None:
    response = await call("GET", "/v1/probe/http-code")

    assert response.headers["WWW-Authenticate"] == "Bearer"
    body = envelope(response)
    assert body["error"]["code"] == body["detail"] == "token_expired"


async def test_an_http_exception_below_a_yield_dependency_keeps_its_status_and_code() -> None:
    response = await call("GET", "/v1/probe/under-yield-dependency")

    assert response.status_code == 422
    assert envelope(response)["error"]["code"] == "mindmap_unavailable"


async def test_a_sentence_in_an_http_exception_is_replaced_by_the_status_code() -> None:
    body = envelope(await call("GET", "/v1/probe/http-sentence"))

    assert body["error"]["code"] == body["detail"] == "forbidden"


async def test_an_unknown_v1_path_is_a_json_404() -> None:
    body = envelope(await call("GET", "/v1/scripts"))

    assert body["error"]["code"] == "not_found"


async def test_a_wrong_method_is_405_with_the_allowed_ones() -> None:
    response = await call("POST", "/v1/health")

    assert response.headers["Allow"] == "GET"
    assert envelope(response)["error"]["code"] == "method_not_allowed"


async def test_validation_names_the_fields_and_never_echoes_the_input() -> None:
    response = await call(
        "POST", "/v1/probe/credentials", json={"email": SECRET, "password": SECRET}
    )

    body = envelope(response)
    assert body["error"]["code"] == body["detail"] == "validation_error"
    assert body["error"]["fields"] == [
        {"loc": ["body", "email"], "type": "string_too_long"},
        {"loc": ["body", "password"], "type": "string_too_short"},
    ]
    assert SECRET not in response.text


async def test_a_malformed_json_body_is_a_validation_error() -> None:
    async with client_of(build_probe_app().app) as client:
        response = await client.post(
            "/v1/probe/credentials",
            content=b"{not json",
            headers={"Content-Type": "application/json"},
        )

    assert response.status_code == 422
    assert envelope(response)["error"]["fields"][0]["type"] == "json_invalid"


async def test_an_unhandled_error_is_one_500_without_internals_and_one_log_line() -> None:
    with captured_logs() as captured:
        response = await call("GET", "/v1/probe/crash")

    assert response.status_code == 500
    body = envelope(response)
    assert body["error"]["code"] == body["detail"] == "internal_error"
    assert SECRET not in response.text
    [line] = captured.lines()
    assert line["level"] == "error"
    assert line["request_id"] == body["error"]["request_id"]
    assert line["route"] == "/v1/probe/crash"
    assert line["status"] == 500
    assert "RuntimeError" in line["exception"]


@pytest.mark.parametrize(
    "handler", [render_app_error, render_http_exception, render_validation_error]
)
async def test_a_handler_given_a_foreign_exception_raises_it_again(
    handler: Callable[[Request, Exception], Awaitable[Response]],
) -> None:
    foreign = LookupError("не тот тип")

    with pytest.raises(LookupError):
        await handler(Request({"type": "http"}), foreign)
