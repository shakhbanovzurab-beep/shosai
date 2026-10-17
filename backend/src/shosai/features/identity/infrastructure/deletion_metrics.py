"""Metrics of the erasure saga (identity plan §3.10).

Labels come from closed sets: an owner declared in code, two outcomes, two homes. The
alert "a deletion saga not finished after 1 h" reads the age of the oldest erasure; the
nfr-13 monitor pages on any leftover the check after erasure finds.
"""

from typing import Literal

from prometheus_client import CollectorRegistry, Counter, Gauge

from shosai.core.kernel.homes import Home

type StepOutcome = Literal["erased", "failed"]


class DeletionMetrics:
    """Erasure steps by owner and outcome, and how long the oldest erasure has run."""

    def __init__(self, registry: CollectorRegistry) -> None:
        self._steps = Counter(
            "shosai_identity_deletion_steps",
            "Шаги саги стирания аккаунта по владельцу данных и исходу",
            ("handler", "outcome"),
            registry=registry,
        )
        self._leftovers = Counter(
            "shosai_identity_erasure_leftovers",
            "Места с данными человека, найденные проверкой после стирания, по владельцу",
            ("handler",),
            registry=registry,
        )
        self._oldest = Gauge(
            "shosai_identity_erasure_oldest_age_seconds",
            "Сколько секунд идёт самое старое незаконченное стирание аккаунта в доме",
            ("home",),
            registry=registry,
        )

    def step(self, owner: str, outcome: StepOutcome) -> None:
        """One handler run of the saga."""
        self._steps.labels(handler=owner, outcome=outcome).inc()

    def leftovers(self, owner: str, places: int) -> None:
        """Tables, prefixes or grants of an erased account the owner still holds (nfr-13)."""
        self._leftovers.labels(handler=owner).inc(places)

    def oldest(self, home: Home, seconds: float) -> None:
        """The age of the home's oldest erasure; zero when none runs."""
        self._oldest.labels(home=home.value).set(seconds)
