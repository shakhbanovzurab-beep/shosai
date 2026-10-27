"""The outermost middleware of a public app (ADR 0008, target architecture §16.1, §16.2).

Every request gets an id, kept from the client or generated, and a log context carrying
it. Every response gets the common headers: `X-Request-ID` and the security headers.
One access line records the method, the route template, the status and the duration,
and the same outcome feeds the HTTP metrics once per request. An exception no handler
took becomes the 500 envelope here and is logged once, on that same line, with its
stack. No response leaves the app without its request id.

The route template comes from FastAPI's routing result (`RouteTemplates`); the boundary
never matches the path again.

Pure ASGI: under the draft's `BaseHTTPMiddleware` an `HTTPException` raised below a
dependency with `yield` turned into a 500.
"""

import time
from collections.abc import Mapping

import structlog
from opentelemetry import trace
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from shosai.core.observability.log_context import late_log_fields, log_context
from shosai.core.web.envelope import error_body, error_response
from shosai.core.web.error_handlers import status_code
from shosai.core.web.http_metrics import CompletedRequest, HttpMetrics
from shosai.core.web.request_facts import RequestFacts, attach_facts
from shosai.core.web.request_ids import REQUEST_ID_HEADER, assign_request_id
from shosai.core.web.route_templates import RouteTemplates

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
    """Request id, log context, common headers, access line, metrics and the last 500."""

    def __init__(self, app: ASGIApp, metrics: HttpMetrics, templates: RouteTemplates) -> None:
        self.app = app
        self._metrics = metrics
        self._templates = templates

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Run the request inside its context; other ASGI scopes pass through."""
        if scope["type"] not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return
        request_id = assign_request_id(scope)
        facts = attach_facts(scope)
        with log_context(request_id=request_id), late_log_fields(facts.log_fields):
            if scope["type"] == "http":
                exchange = _HttpExchange(self.app, scope, request_id, self._templates, facts)
                try:
                    await exchange.run(receive, send)
                finally:
                    # Как у инструментатора: запись и при отмене задачи посреди запроса.
                    self._metrics.observe(exchange.completed())
            else:
                # Сокетам — контекст логов; их коды закрытия и время жизни считает шлюз
                # (core/web/sockets.py).
                await self.app(scope, receive, send)


class _HttpExchange:
    """One HTTP request passing the boundary: its response status, size and timing."""

    def __init__(
        self,
        app: ASGIApp,
        scope: Scope,
        request_id: str,
        templates: RouteTemplates,
        facts: RequestFacts,
    ) -> None:
        self._app = app
        self._scope = scope
        self._request_id = request_id
        self._templates = templates
        self._facts = facts
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

    def completed(self) -> CompletedRequest:
        """The outcome for the HTTP metrics; `status` stays None when no response started."""
        return CompletedRequest(
            method=str(self._scope.get("method", "")),
            route=self._templates.of(self._scope),
            status=self._status,
            scheme=str(self._scope.get("scheme", "")),
            duration_seconds=time.perf_counter() - self._started,
            trace_id=current_trace_id(),
            home=self._facts.home,
        )

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
            "route": self._templates.of(self._scope) or UNMATCHED_ROUTE,
            "status": self._status,
            "duration_ms": round((time.perf_counter() - self._started) * 1000, 3),
        }


def current_trace_id() -> str | None:
    """The trace of the request's server span, in the hex form logs and Tempo use."""
    context = trace.get_current_span().get_span_context()
    return format(context.trace_id, "032x") if context.is_valid else None
