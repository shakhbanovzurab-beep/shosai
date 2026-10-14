"""Metrics of the account transfer saga (identity plan §3.10).

Labels come from closed sets: a step of the saga, two outcomes, two homes. An alert reads
the age of the oldest open transfer: one open for hours has stalled.
"""

from typing import Literal

from prometheus_client import CollectorRegistry, Counter, Gauge

from shosai.core.kernel.homes import Home

type StepOutcome = Literal["done", "failed"]


class TransferMetrics:
    """Saga steps by step and outcome, and how long the oldest open transfer has run."""

    def __init__(self, registry: CollectorRegistry) -> None:
        self._steps = Counter(
            "shosai_identity_transfer_steps",
            "Шаги саги переноса аккаунта между домами по шагу и исходу",
            ("step", "outcome"),
            registry=registry,
        )
        self._oldest = Gauge(
            "shosai_identity_transfer_oldest_age_seconds",
            "Сколько секунд идёт самый старый незаконченный перенос из дома",
            ("home",),
            registry=registry,
        )

    def step(self, step: str, outcome: StepOutcome) -> None:
        """One step of the saga."""
        self._steps.labels(step=step, outcome=outcome).inc()

    def oldest(self, home: Home, seconds: float) -> None:
        """The age of the home's oldest open transfer; zero when none is open."""
        self._oldest.labels(home=home.value).set(seconds)
