"""The Decision Layer in numbers (Leo §11.3, decisions plan §3.8): closed labels, no ids, no text.

`shosai_decision_requests_total{point, source, reason, changed}` counts every decision a
consumer asked for — settled by the rule, a fallback, Jev, or late — and whether the outcome
differs from the rule's; `shosai_decision_seconds{point, source}` is the time the caller
waited. `shosai_decision_late_total{point}` counts answers that came after their deadline,
`shosai_decision_records_lost_total` the records a write could not keep. The invariant
`shosai_decision_unsafe_outcomes_total{point}` — an outcome less careful than its rule —
must stay at zero; a policy that breaks it is answered with the rule's outcome and pages.
"""

from typing import Final

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

UNSAFE_OUTCOMES: Final = "shosai_decision_unsafe_outcomes_total"
REQUESTS: Final = "shosai_decision_requests_total"
DECISION_SECONDS: Final = "shosai_decision_seconds"
DECISION_BUCKETS: Final = (0.001, 0.005, 0.025, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 1, 2)


class DecisionMetrics:
    """The decisions' counters and times, in the process's registry."""

    def __init__(self, registry: CollectorRegistry) -> None:
        self._requests = Counter(
            REQUESTS.removesuffix("_total"),
            "Решения по точке, источнику, причине и тому, изменили ли они исход правила",
            ("point", "source", "reason", "changed"),
            registry=registry,
        )
        self._seconds = Histogram(
            DECISION_SECONDS,
            "Сколько вызывающий ждал решения",
            ("point", "source"),
            buckets=DECISION_BUCKETS,
            registry=registry,
        )
        self._late = Counter(
            "shosai_decision_late",
            "Ответы Jev, пришедшие после срока решения",
            ("point",),
            registry=registry,
        )
        self._lost = Counter(
            "shosai_decision_records_lost",
            "Записи решений и исходов, которые не удалось сохранить",
            ("table",),
            registry=registry,
        )
        self._unsafe = Counter(
            UNSAFE_OUTCOMES.removesuffix("_total"),
            "Исходы политики мягче правила: инвариант, должен быть нулём",
            ("point",),
            registry=registry,
        )
        self._in_flight = Gauge(
            "shosai_decision_in_flight",
            "Вызовы Jev этого процесса в полёте, опоздавшие тоже",
            registry=registry,
        )

    def decided(
        self, point: str, source: str, reason: str, *, changed: bool, seconds: float
    ) -> None:
        """A decision returned to its caller after `seconds`."""
        mark = "yes" if changed else "no"
        self._requests.labels(point=point, source=source, reason=reason, changed=mark).inc()
        self._seconds.labels(point=point, source=source).observe(seconds)

    def late(self, point: str) -> None:
        """Jev answered after the caller had the rule's outcome."""
        self._late.labels(point=point).inc()

    def lost(self, table: str, rows: int) -> None:
        """Rows a write could not keep."""
        self._lost.labels(table=table).inc(rows)

    def unsafe(self, point: str) -> None:
        """A policy's outcome was less careful than its rule's."""
        self._unsafe.labels(point=point).inc()

    def in_flight(self, calls: int) -> None:
        """Jev calls of the process now in flight."""
        self._in_flight.set(calls)
