"""The outermost middleware of a public app (ADR 0008, target architecture §16.1, §16.2).

Every request gets an id, kept from the client or generated, and a log context carrying
it. Every response gets the common headers: `X-Request-ID` and the security headers.
One access line records the method, the route template, the status and the duration.
An exception no handler took becomes the 500 envelope here and is logged once, on that
same line, with its stack. No response leaves the app without its request id.

Pure ASGI: under the draft's `BaseHTTPMiddleware` an `HTTPException` raised below a
dependency with `yield` turned into a 500.
"""

import time
from collections.abc import Mapping

import structlog
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from whisperer.core.observability.log_context import log_context
from whisperer.core.web.envelope import error_body, error_response
from whisperer.core.web.error_handlers import status_code
from whisperer.core.web.request_ids import REQUEST_ID_HEADER, assign_request_id

log = structlog.stdlib.get_logger(__name__)

UNMATCHED_ROUTE = "unmatched"
HTTPS_SCHEME = "https"
# Год, без includeSubDomains и preload, как в черновике: у поддоменов может не быть TLS,
# а preload-список не откатить. По HTTP заголовок не шлётся (RFC 6797 §7.2).
STRICT_TRANSPORT_SECURITY = ("Strict-Transport-Security", "max-age=31536000")
# Те же значения, что ставит edge черновика (deploy/nginx/snippets/security-headers.conf).
SECURITY_HEADERS: Mapping[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}
SERVER_ERROR_STATUS = 500


class RequestBoundary:
    """Request id, log context, common headers, access line and the last-resort 500."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Run the request inside its context; other ASGI scopes pass through."""
        if scope["type"] not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return
        request_id = assign_request_id(scope)
        with log_context(request_id=request_id):
            if scope["type"] == "http":
                await _HttpExchange(self.app, scope, request_id).run(receive, send)
            else:
                # Кадры и коды закрытия WebSocket — забота S05; здесь только контекст логов.
                await self.app(scope, receive, send)


def route_template(scope: Scope) -> str:
    """The template of the matched route, `/v1/items/{item_id}`; never the raw path."""
    route = scope.get("route")
    template = getattr(route, "path_format", None)
    return template if isinstance(template, str) else UNMATCHED_ROUTE


class _HttpExchange:
    """One HTTP request passing the boundary: its response status and timing."""

    def __init__(self, app: ASGIApp, scope: Scope, request_id: str) -> None:
        self._app = app
        self._scope = scope
        self._request_id = request_id
        self._status: int | None = None
        self._started = time.perf_counter()

    async def run(self, receive: Receive, send: Send) -> None:
        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                self._status = int(message["status"])
                self._add_headers(MutableHeaders(scope=message))
            await send(message)

        try:
            await self._app(self._scope, receive, send_with_headers)
        except Exception:
            # Последний рубеж: обработчики приложения исключение не взяли.
            if self._status is not None:
                # Статус уже ушёл клиенту, нового ответа не отправить. Не пробрасываем,
                # чтобы сервер не записал ту же ошибку второй раз; незавершённый ответ
                # он оборвёт сам.
                log.exception("Ответ оборван ошибкой", **self._outcome())
                return
            self._status = SERVER_ERROR_STATUS
            log.exception("Необработанная ошибка запроса", **self._outcome())
            await self._answer_internal_error(receive, send_with_headers)
            return
        if self._status is None:
            log.error("Приложение не отправило ответ", **self._outcome())
        elif self._status >= SERVER_ERROR_STATUS:
            log.warning("Запрос завершён ошибкой сервера", **self._outcome())
        else:
            log.info("Запрос обработан", **self._outcome())

    async def _answer_internal_error(self, receive: Receive, send: Send) -> None:
        code = status_code(SERVER_ERROR_STATUS)
        response = error_response(SERVER_ERROR_STATUS, error_body(code, self._request_id))
        await response(self._scope, receive, send)

    def _add_headers(self, headers: MutableHeaders) -> None:
        headers[REQUEST_ID_HEADER] = self._request_id
        for name, value in SECURITY_HEADERS.items():
            headers.setdefault(name, value)
        if self._scope.get("scheme") == HTTPS_SCHEME:
            headers.setdefault(*STRICT_TRANSPORT_SECURITY)

    def _outcome(self) -> dict[str, object]:
        return {
            "method": self._scope.get("method"),
            "route": route_template(self._scope),
            "status": self._status,
            "duration_ms": round((time.perf_counter() - self._started) * 1000, 3),
        }
