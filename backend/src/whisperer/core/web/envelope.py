"""The one error body of the HTTP API (ADR 0008) and its place in OpenAPI.

`{"error": {code, request_id, params?, fields?}, "detail": …}`: `error` is for v2
clients, `detail` keeps what shipped native clients read and defaults to the code.
"""

from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict
from pydantic.json_schema import SkipJsonSchema
from starlette.responses import Response

from whisperer.core.kernel.errors import CompatibleDetail, DetailValue, ErrorParam

JSON_MEDIA_TYPE = "application/json"


class InvalidField(BaseModel):
    """Where a request failed validation and why; the submitted value is never echoed."""

    model_config = ConfigDict(frozen=True)

    loc: tuple[str | int, ...]
    type: str


class ErrorDescription(BaseModel):
    """The machine-readable error: a stable code, the request id and optional context."""

    model_config = ConfigDict(frozen=True)

    code: str
    request_id: str
    # SkipJsonSchema: в схеме поле необязательное, но не nullable — в теле его либо нет,
    # либо оно заполнено.
    params: dict[str, ErrorParam] | SkipJsonSchema[None] = None
    fields: list[InvalidField] | SkipJsonSchema[None] = None


class ErrorResponse(BaseModel):
    """Body of every error response of the HTTP API.

    `error.code` is the stable code a client turns into text; `error.request_id` equals
    the `X-Request-ID` header. `detail` is kept for shipped clients: the code by default,
    the draft's shape on routes whose draft contract had another one.
    """

    model_config = ConfigDict(frozen=True)

    error: ErrorDescription
    detail: str | dict[str, DetailValue]


# Ответ `default` в OpenAPI покрывает все статусы, не объявленные отдельно, — то есть
# ошибки; заодно FastAPI не подставляет свою схему HTTPValidationError для 422.
ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    "default": {
        "model": ErrorResponse,
        "description": "Error. The body is the error envelope; see `ErrorResponse`.",
    }
}


def error_body(
    code: str,
    request_id: str,
    *,
    params: Mapping[str, ErrorParam] | None = None,
    fields: Sequence[InvalidField] | None = None,
    detail: CompatibleDetail | None = None,
) -> ErrorResponse:
    """The envelope of one error; `detail` repeats the code unless a compatible one is given."""
    return ErrorResponse(
        error=ErrorDescription(
            code=code,
            request_id=request_id,
            params=dict(params) if params else None,
            fields=list(fields) if fields is not None else None,
        ),
        detail=code if detail is None else _plain(detail),
    )


def error_response(
    status: int, body: ErrorResponse, headers: Mapping[str, str] | None = None
) -> Response:
    """The envelope as a JSON response, serialized by Pydantic; absent parts are left out."""
    return Response(
        body.model_dump_json(exclude_none=True),
        status_code=int(status),
        media_type=JSON_MEDIA_TYPE,
        headers=headers,
    )


def _plain(detail: CompatibleDetail) -> str | dict[str, DetailValue]:
    return detail if isinstance(detail, str) else dict(detail)
