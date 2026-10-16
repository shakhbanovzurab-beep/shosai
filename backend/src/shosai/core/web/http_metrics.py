"""HTTP RED metric of a public app, recorded by the request boundary (§16.1, §16.7).

One histogram under the OpenTelemetry semantic conventions for HTTP servers, as the
Prometheus exporter of the OpenTelemetry SDK names it: `http.server.request.duration` →
`http_server_request_duration_seconds`, its attributes with dots as underscores, its
advisory buckets (ADR 0012, amended by F1 audit OD-3). Rate, errors and duration all come
from it. The boundary passes the template of the route FastAPI has already matched;
nothing is matched again. Every label value comes from a closed set: a served route
template or empty, a known method or `_OTHER`, a status code the application chose, a
scheme of two values, an error type derived from the status, and `home` — the caller's data
home (`ru`, `eu`) or empty for an anonymous request (§16.7; ADR 0012 amended by F5).

A request the collector's tail sampling always keeps — a server error, no response, or
slower than `SLOW_REQUEST_SECONDS` — carries its `trace_id` as an exemplar, so a latency
panel leads to a trace that exists (§16.1, F5 plan §3.6). Other requests carry none: 95%
of their traces are dropped.
"""

from dataclasses import dataclass

from prometheus_client import CollectorRegistry, Histogram

from shosai.core.kernel.homes import Home

DURATION_METRIC = "http_server_request_duration_seconds"
DURATION_HELP = "Duration of HTTP server requests."
METHOD_LABEL = "http_request_method"
ROUTE_LABEL = "http_route"
STATUS_LABEL = "http_response_status_code"
SCHEME_LABEL = "url_scheme"
ERROR_LABEL = "error_type"
HOME_LABEL = "home"
LABELS = (METHOD_LABEL, ROUTE_LABEL, STATUS_LABEL, SCHEME_LABEL, ERROR_LABEL, HOME_LABEL)
# Атрибут, которого нет, в Prometheus — пустая метка: так экспортёр OpenTelemetry пишет
# запрос без маршрута, без ответа или без ошибки.
ABSENT = ""
OTHER = "_OTHER"
# Методы RFC 9110 и QUERY — тот же набор, что у FastAPI и OpenTelemetry. Любой другой
# токен метода выбирает клиент; в метке он размножил бы временные ряды.
KNOWN_METHODS = frozenset(
    {"CONNECT", "DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT", "QUERY", "TRACE"}
)
HTTPS_SCHEME = "https"
HTTP_SCHEME = "http"
SERVER_ERROR_STATUS = 500
# Порог медленного запроса — тот же, что у хвостовой выборки коллектора (политика
# slow-http-requests в deploy/observability/collector/config.yaml): трейс такого запроса
# сохраняется всегда, и exemplar на него ведёт. Меняются только вместе.
SLOW_REQUEST_SECONDS = 0.3
EXEMPLAR_TRACE_ID = "trace_id"
# Рекомендованные корзины семантических соглашений для http.server.request.duration и
# корзина на пороге цели задержки §16.3 (300 мс): SLI задержки — доля запросов не дольше
# порога, а её читают только по границе корзины (ADR 0012, поправка F5).
DURATION_BUCKETS = (
    0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.3, 0.5, 0.75, 1, 2.5, 5, 7.5, 10, float("inf"),
)  # fmt: skip


@dataclass(frozen=True, slots=True)
class CompletedRequest:
    """What the boundary knows once the request is done.

    `route` is None when routing matched nothing; `status` is None when no response
    started, because the task was cancelled or the application sent nothing; `trace_id`
    is None outside a recorded span.
    """

    method: str
    route: str | None
    status: int | None
    scheme: str
    duration_seconds: float
    trace_id: str | None
    home: Home | None = None


class HttpMetrics:
    """The HTTP server duration histogram of the process registry."""

    def __init__(self, registry: CollectorRegistry) -> None:
        self._duration = Histogram(
            DURATION_METRIC, DURATION_HELP, LABELS, buckets=DURATION_BUCKETS, registry=registry
        )

    def observe(self, request: CompletedRequest) -> None:
        """Record one request; labels never carry the path, the query or a client's method."""
        status, error = status_labels(request.status)
        self._duration.labels(
            request.method if request.method in KNOWN_METHODS else OTHER,
            request.route or ABSENT,
            status,
            HTTPS_SCHEME if request.scheme == HTTPS_SCHEME else HTTP_SCHEME,
            error,
            request.home.value if request.home is not None else ABSENT,
        ).observe(request.duration_seconds, exemplar_of(request, failed=error != ABSENT))


def exemplar_of(request: CompletedRequest, *, failed: bool) -> dict[str, str] | None:
    """The trace of a request whose trace is always kept; None for every other request."""
    if request.trace_id is None:
        return None
    if failed or request.duration_seconds > SLOW_REQUEST_SECONDS:
        return {EXEMPLAR_TRACE_ID: request.trace_id}
    return None


def status_labels(status: int | None) -> tuple[str, str]:
    """The status code and error type labels.

    A 5xx response is an error typed by its code, as the conventions say; a request with
    no response has no code and the error type `_OTHER`. A status outside 100…599 cannot
    be a valid response and counts as 500.
    """
    if status is None:
        return ABSENT, OTHER
    code = status if 100 <= status <= 599 else SERVER_ERROR_STATUS
    return str(code), str(code) if code >= SERVER_ERROR_STATUS else ABSENT
