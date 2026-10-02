"""Every expected error path of the HTTP API rendered as the one envelope (ADR 0008).

Domain errors (`AppError`), HTTP exceptions of FastAPI and Starlette (an unknown path,
a method not allowed, security schemes) and request validation. An unhandled exception
never reaches these handlers: the request boundary renders it as the 500 envelope.
"""

import math
from http import HTTPStatus

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import Response

from whisperer.core.kernel.errors import ERROR_CODE, AppError
from whisperer.core.web.envelope import InvalidField, error_body, error_response
from whisperer.core.web.request_ids import request_id_of

VALIDATION_ERROR = "validation_error"
RETRY_AFTER_PARAM = "retry_after_seconds"
# Коды статусов — часть контракта: клиент переводит код в текст через i18n, поэтому
# таблица явная, а не выводится из фразы статуса, которая меняется между версиями Python.
STATUS_CODES: dict[int, str] = {
    HTTPStatus.BAD_REQUEST: "bad_request",
    HTTPStatus.UNAUTHORIZED: "unauthorized",
    HTTPStatus.PAYMENT_REQUIRED: "payment_required",
    HTTPStatus.FORBIDDEN: "forbidden",
    HTTPStatus.NOT_FOUND: "not_found",
    HTTPStatus.METHOD_NOT_ALLOWED: "method_not_allowed",
    HTTPStatus.NOT_ACCEPTABLE: "not_acceptable",
    HTTPStatus.CONFLICT: "conflict",
    HTTPStatus.GONE: "gone",
    HTTPStatus.CONTENT_TOO_LARGE: "content_too_large",
    HTTPStatus.UNSUPPORTED_MEDIA_TYPE: "unsupported_media_type",
    HTTPStatus.UNPROCESSABLE_CONTENT: VALIDATION_ERROR,
    HTTPStatus.TOO_MANY_REQUESTS: "rate_limited",
    HTTPStatus.INTERNAL_SERVER_ERROR: "internal_error",
    HTTPStatus.NOT_IMPLEMENTED: "not_implemented",
    HTTPStatus.BAD_GATEWAY: "bad_gateway",
    HTTPStatus.SERVICE_UNAVAILABLE: "service_unavailable",
    HTTPStatus.GATEWAY_TIMEOUT: "gateway_timeout",
}


def install_error_handlers(app: FastAPI) -> None:
    """Register the handlers of every expected error path on the app."""
    app.add_exception_handler(AppError, render_app_error)
    app.add_exception_handler(HTTPException, render_http_exception)
    app.add_exception_handler(RequestValidationError, render_validation_error)


def status_code(status: int) -> str:
    """The stable code of an HTTP status without a more specific one: `not_found`, `http_418`."""
    return STATUS_CODES.get(status, f"http_{status}")


# Starlette объявляет обработчик принимающим любое исключение; сужаем внутри, иначе
# сигнатура нарушала бы подстановку. Обработчики асинхронные: синхронный Starlette
# увёл бы в пул потоков.
async def render_app_error(request: Request, error: Exception) -> Response:
    """A domain error: its code, status, params and compatible `detail`."""
    if not isinstance(error, AppError):
        raise error
    retry_after = error.params.get(RETRY_AFTER_PARAM)
    headers = None
    if isinstance(retry_after, int | float) and not isinstance(retry_after, bool):
        headers = {"Retry-After": str(max(math.ceil(retry_after), 0))}
    body = error_body(
        error.code, request_id_of(request.scope), params=error.params, detail=error.detail
    )
    return error_response(error.status, body, headers)


async def render_http_exception(request: Request, error: Exception) -> Response:
    """An HTTP exception: a code-like `detail` becomes the code, a sentence is dropped.

    Its headers (`Allow` on 405, `WWW-Authenticate` on 401) are kept.
    """
    if not isinstance(error, HTTPException):
        raise error
    # Starlette объявляет detail строкой, но HTTPException из FastAPI несёт любое значение.
    detail: object = error.detail
    code = (
        detail
        if isinstance(detail, str) and ERROR_CODE.fullmatch(detail)
        else status_code(error.status_code)
    )
    return error_response(
        error.status_code, error_body(code, request_id_of(request.scope)), error.headers
    )


async def render_validation_error(request: Request, error: Exception) -> Response:
    """422 with the location and type of each invalid field and nothing of the input."""
    if not isinstance(error, RequestValidationError):
        raise error
    fields = [InvalidField(loc=tuple(item["loc"]), type=item["type"]) for item in error.errors()]
    body = error_body(VALIDATION_ERROR, request_id_of(request.scope), fields=fields)
    return error_response(HTTPStatus.UNPROCESSABLE_CONTENT, body)
