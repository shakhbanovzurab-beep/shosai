"""HTTP RED metrics of a public app, recorded by the request boundary (§16.1, §16.7).

Names, types, help texts, label names and buckets are those of
prometheus-fastapi-instrumentator 8.1.0 (`metrics.default()`), which the project used
before (ADR 0012), so dashboards and alerts keep working. The boundary passes the
template of the route FastAPI has already matched; nothing is matched again. Every label
value comes from a closed set: a served route template or `none`, a known method or
`_OTHER`, a status class.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from prometheus_client import CollectorRegistry, Counter, Histogram, Summary

UNMATCHED_HANDLER = "none"
OTHER_METHOD = "_OTHER"
# Методы RFC 9110 и QUERY — тот же набор, что у FastAPI и OpenTelemetry. Любой другой
# токен метода выбирает клиент; в метке он размножил бы временные ряды.
KNOWN_METHODS = frozenset(
    {"CONNECT", "DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT", "QUERY", "TRACE"}
)
# Корзины и тексты — дословно из metrics.default() инструментатора 8.1.0.
LATENCY_HIGHR_BUCKETS = (
    0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5, 7.5,
    10, 30, 60, float("inf"),
)  # fmt: skip
LATENCY_LOWR_BUCKETS = (0.1, 0.5, 1, float("inf"))
SIZE_HELP_TAIL = "Only value of header is respected. Otherwise ignored. No percentile calculated. "


@dataclass(frozen=True, slots=True)
class CompletedRequest:
    """What the boundary knows once the response is done; `handler` is None when unmatched."""

    method: str
    handler: str | None
    status: int
    duration_seconds: float
    request_bytes: int
    response_bytes: int


class HttpMetrics:
    """The five HTTP metrics of the process registry."""

    def __init__(self, registry: CollectorRegistry) -> None:
        self._requests = Counter(
            "http_requests_total",
            "Total number of requests by method, status and handler.",
            ("method", "status", "handler"),
            registry=registry,
        )
        self._request_size = Summary(
            "http_request_size_bytes",
            "Content length of incoming requests by handler. " + SIZE_HELP_TAIL,
            ("handler",),
            registry=registry,
        )
        self._response_size = Summary(
            "http_response_size_bytes",
            "Content length of outgoing responses by handler. " + SIZE_HELP_TAIL,
            ("handler",),
            registry=registry,
        )
        self._latency_highr = Histogram(
            "http_request_duration_highr_seconds",
            "Latency with many buckets but no API specific labels. "
            "Made for more accurate percentile calculations. ",
            buckets=LATENCY_HIGHR_BUCKETS,
            registry=registry,
        )
        self._latency = Histogram(
            "http_request_duration_seconds",
            "Latency with only few buckets by handler. "
            "Made to be only used if aggregation by handler is important. ",
            ("method", "handler"),
            buckets=LATENCY_LOWR_BUCKETS,
            registry=registry,
        )

    def observe(self, request: CompletedRequest) -> None:
        """Record one request; labels never carry the path, the query or a client's method."""
        handler = request.handler or UNMATCHED_HANDLER
        method = request.method if request.method in KNOWN_METHODS else OTHER_METHOD
        status = status_class(request.status)
        self._requests.labels(method, status, handler).inc()
        self._request_size.labels(handler).observe(request.request_bytes)
        self._response_size.labels(handler).observe(request.response_bytes)
        self._latency_highr.observe(request.duration_seconds)
        self._latency.labels(method, handler).observe(request.duration_seconds)


def status_class(status: int) -> str:
    """`2xx` for 200…299; a status outside 100…599 is a server error, `5xx`."""
    return f"{status // 100}xx" if 100 <= status <= 599 else "5xx"


def content_length(headers: Iterable[tuple[bytes, bytes]]) -> int:
    """The `Content-Length` of raw ASGI headers, 0 when absent or malformed; never raises."""
    for name, value in headers:
        if name.lower() == b"content-length":
            # bytes.isdigit признаёт только ASCII-цифры; у str «¹» тоже цифра, а int() падает.
            digits = value.strip()
            return int(digits) if digits.isdigit() else 0
    return 0
