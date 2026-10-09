"""OpenAPI documents the envelope for every error status; API docs follow the setting."""

from typing import Any

import pytest

from shosai.core.config.sections import WebSettings
from tests.core.web.probe_app import build_probe_app, client_of

ERROR_RESPONSE_REF = "#/components/schemas/ErrorResponse"
DOCS_PATHS = ["/openapi.json", "/docs", "/redoc"]


def operations(schema: dict[str, Any]) -> list[dict[str, Any]]:
    """Every operation of the document."""
    return [operation for path in schema["paths"].values() for operation in path.values()]


def test_every_operation_answers_errors_with_the_envelope() -> None:
    schema = build_probe_app().app.openapi()

    for operation in operations(schema):
        default = operation["responses"]["default"]
        assert default["content"]["application/json"]["schema"]["$ref"] == ERROR_RESPONSE_REF
        assert "422" not in operation["responses"]
    assert "HTTPValidationError" not in schema["components"]["schemas"]


def test_optional_parts_of_the_envelope_are_absent_rather_than_null() -> None:
    schemas = build_probe_app().app.openapi()["components"]["schemas"]

    description = schemas["ErrorDescription"]
    assert description["required"] == ["code", "request_id"]
    for name in ("params", "fields"):
        assert "null" not in str(description["properties"][name])
    assert schemas["ErrorResponse"]["required"] == ["error", "detail"]


async def test_api_docs_are_closed_by_default() -> None:
    async with client_of(build_probe_app().app) as client:
        statuses = [(await client.get(path)).status_code for path in DOCS_PATHS]

    assert statuses == [404, 404, 404]


@pytest.mark.parametrize("path", DOCS_PATHS)
async def test_api_docs_open_when_enabled(path: str) -> None:
    app = build_probe_app(WebSettings(api_docs_enabled=True)).app
    async with client_of(app) as client:
        response = await client.get(path)

    assert response.status_code == 200
