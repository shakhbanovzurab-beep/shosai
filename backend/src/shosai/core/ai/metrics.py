"""Metrics of the provider port's money: calls billed, rows recorded, cost (§16.4, §16.5).

Labels come from closed sets (F6-C17): a provider, a call kind, a call class, a failure
code, a cost source. Three counters make the invariant monitor of §16.4: every call a
provider charged for is `shosai_ai_calls_billed_total`; each becomes a row
(`shosai_ai_cost_rows_recorded_total`), a deferred row, a recognised repeat of its effect
key, or `shosai_ai_calls_without_cost_row_total`, which pages. The hourly reconciliation
holds the same balance against the table itself. Cost is counted in micro-USD per
provider and class; Grafana shows its rate as cost per hour.
"""

from prometheus_client import CollectorRegistry, Counter

from shosai.core.ai.costs.entries import CostEntry
from shosai.core.ai.spend.counters import micro_usd


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
        self._billed = Counter(
            "shosai_ai_calls_billed",
            "Вызовы, за которые провайдер взял деньги: каждому нужна строка стоимости",
            ("provider", "kind", "call_class"),
            registry=registry,
        )
        self._spent = Counter(
            "shosai_ai_cost_microusd",
            "Стоимость записанных вызовов в микродолларах по провайдеру и классу",
            ("provider", "call_class"),
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

    def billed(self, provider: str, kind: str, call_class: str) -> None:
        """A call the provider charged for."""
        self._billed.labels(provider=provider, kind=kind, call_class=call_class).inc()

    def recorded(self, entry: CostEntry) -> None:
        """A cost row written, and what it cost."""
        self._rows.labels(source=entry.cost_source).inc()
        self._spent.labels(provider=entry.provider, call_class=entry.call_class).inc(
            micro_usd(entry.cost_usd)
        )

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
