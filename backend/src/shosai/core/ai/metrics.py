"""Metrics of the provider port that step 2 needs; the full telemetry comes with F6 step 9.

Labels come from closed sets: a provider, a call kind, a failure code, a cost source.
`shosai_ai_calls_without_cost_row_total` counts the calls whose cost was lost — the monitor
of §16.4 pages on it.
"""

from prometheus_client import CollectorRegistry, Counter


class AiMetrics:
    """Refused calls, recorded and deferred cost rows, and the calls that lost their row."""

    def __init__(self, registry: CollectorRegistry) -> None:
        self._refused = Counter(
            "shosai_ai_calls_refused",
            "Вызовы моделей, отклонённые до отправки провайдеру",
            ("kind", "code"),
            registry=registry,
        )
        self._rows = Counter(
            "shosai_ai_cost_rows_recorded",
            "Записанные строки стоимости вызовов по источнику суммы",
            ("source",),
            registry=registry,
        )
        self._deferred = Counter(
            "shosai_ai_cost_rows_deferred",
            "Строки стоимости, отложенные в задачу: дом не принял запись",
            registry=registry,
        )
        self._lost = Counter(
            "shosai_ai_calls_without_cost_row",
            "Оплаченные вызовы, стоимость которых не записана и не отложена",
            registry=registry,
        )
        self._unreported = Counter(
            "shosai_ai_reported_cost_missing",
            "Ответы, где провайдер не назвал стоимость: она посчитана по ценам",
            ("kind",),
            registry=registry,
        )
        self._without_rate = Counter(
            "shosai_ai_cost_rows_without_rate",
            "Строки стоимости без рублей: курса ЦБ ещё нет",
            registry=registry,
        )

    def refused(self, kind: str, code: str) -> None:
        """A call refused before it was sent."""
        self._refused.labels(kind=kind, code=code).inc()

    def recorded(self, source: str) -> None:
        """A cost row written."""
        self._rows.labels(source=source).inc()

    def deferred(self) -> None:
        """A cost row handed to the deferred-record task."""
        self._deferred.inc()

    def lost(self) -> None:
        """A paid call whose cost could be neither written nor deferred."""
        self._lost.inc()

    def unreported(self, kind: str) -> None:
        """A provider answer without the cost it should have reported."""
        self._unreported.labels(kind=kind).inc()

    def without_rate(self) -> None:
        """A cost row written without rubles."""
        self._without_rate.inc()
