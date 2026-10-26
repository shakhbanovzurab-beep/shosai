"""The native model proxy in numbers (agent step 14): closed label sets, no ids, no text.

`shosai_agent_proxy_answers_total{route, outcome}` counts each request by how it ended:
`refused` before the stream (its code is the HTTP answer's), `answered` with the model's own
finish, `interrupted` by a failure after the first byte. `shosai_agent_proxy_first_piece_seconds
{route}` times the wait for the model's first piece, which the client's headers wait for.
"""

from enum import StrEnum

from prometheus_client import CollectorRegistry, Counter, Histogram

FIRST_PIECE_BUCKETS = (0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 8.0, 13.0, 20.0)


class ProxyRoute(StrEnum):
    """Which of the proxy's routes."""

    CHAT = "chat"
    VISION = "vision"


class ProxyOutcome(StrEnum):
    """How a proxy request ended."""

    REFUSED = "refused"
    ANSWERED = "answered"
    INTERRUPTED = "interrupted"


class ProxyMetrics:
    """The proxy's counters, in the process's registry."""

    def __init__(self, registry: CollectorRegistry) -> None:
        self._answers = Counter(
            "shosai_agent_proxy_answers",
            "Запросы нативного прокси модели по маршруту и исходу",
            ("route", "outcome"),
            registry=registry,
        )
        self._first = Histogram(
            "shosai_agent_proxy_first_piece_seconds",
            "Ожидание первого куска ответа модели в нативном прокси",
            ("route",),
            buckets=FIRST_PIECE_BUCKETS,
            registry=registry,
        )

    def ended(self, route: ProxyRoute, outcome: ProxyOutcome) -> None:
        """A request ended."""
        self._answers.labels(route.value, outcome.value).inc()

    def first_piece(self, route: ProxyRoute, seconds: float) -> None:
        """The model's first piece came, or the wait for it ran out."""
        self._first.labels(route.value).observe(seconds)
