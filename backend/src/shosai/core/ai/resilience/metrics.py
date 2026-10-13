"""Metrics of the port's resilience: retries, breakers, provider slots and fallbacks (§16.5).

Labels come from closed sets (F6-C17): the provider, a decision or state code, the call kind;
the model appears only on breaker metrics, bounded by the rows of the price list.
"""

from typing import Literal

from prometheus_client import CollectorRegistry, Counter

type RetryOutcome = Literal["retried", "budget_spent"]
type SlotDecision = Literal["taken", "waited", "full", "unguarded", "refused"]
type BreakerState = Literal["opened", "closed"]


class ResilienceMetrics:
    """Counts what the resilience of the port decided."""

    def __init__(self, registry: CollectorRegistry) -> None:
        self._retries = Counter(
            "shosai_ai_retries",
            "Повторы вызовов до первого байта и отказы в повторе по бюджету",
            ("provider", "outcome"),
            registry=registry,
        )
        self._breakers = Counter(
            "shosai_ai_breaker_transitions",
            "Открытия и закрытия выключателей по провайдеру и модели",
            ("provider", "model", "state"),
            registry=registry,
        )
        self._rejected = Counter(
            "shosai_ai_breaker_rejections",
            "Вызовы, не отправленные модели: её выключатель открыт",
            ("provider", "model"),
            registry=registry,
        )
        self._slots = Counter(
            "shosai_ai_provider_slots",
            "Решения семафора провайдера: занят слот, ждали, нет мест, без Valkey",
            ("provider", "decision"),
            registry=registry,
        )
        self._fallbacks = Counter(
            "shosai_ai_fallbacks",
            "Вызовы, ответ на которые дала не первая модель маршрута",
            ("provider", "kind"),
            registry=registry,
        )

    def retry(self, provider: str, outcome: RetryOutcome) -> None:
        """A retry sent, or refused by the budget."""
        self._retries.labels(provider=provider, outcome=outcome).inc()

    def breaker(self, provider: str, model: str, state: BreakerState) -> None:
        """A breaker opened or closed."""
        self._breakers.labels(provider=provider, model=model, state=state).inc()

    def rejected(self, provider: str, model: str) -> None:
        """A call skipped by an open breaker."""
        self._rejected.labels(provider=provider, model=model).inc()

    def slot(self, provider: str, decision: SlotDecision) -> None:
        """What the provider's semaphore decided for a call or session."""
        self._slots.labels(provider=provider, decision=decision).inc()

    def fell_back(self, provider: str, kind: str) -> None:
        """A call answered by a fallback model of its route."""
        self._fallbacks.labels(provider=provider, kind=kind).inc()
