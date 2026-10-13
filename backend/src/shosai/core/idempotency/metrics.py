"""Metrics of the effect-key ledger: repeats per scope and expired keys removed (§16.7).

Labels come from closed sets: the scope is a name some slice declared, the outcome one of
two values, the home one of two.
"""

from typing import Literal

from prometheus_client import CollectorRegistry, Counter

from shosai.core.kernel.homes import Home

type RepeatOutcome = Literal["replayed", "reused"]


class EffectKeyMetrics:
    """Repeated keys by scope and outcome, and purged keys by home."""

    def __init__(self, registry: CollectorRegistry) -> None:
        self._repeats = Counter(
            "shosai_effect_key_repeats",
            "Повторы ключа эффекта: исход возвращён или ключ занят другим запросом",
            ("scope", "outcome"),
            registry=registry,
        )
        self._purged = Counter(
            "shosai_effect_keys_purged",
            "Ключи эффектов, удалённые по истечении срока",
            ("home",),
            registry=registry,
        )

    def count_repeat(self, scope: str, outcome: RepeatOutcome) -> None:
        """One repeat of a key that was already recorded."""
        self._repeats.labels(scope=scope, outcome=outcome).inc()

    def count_purged(self, home: Home, count: int) -> None:
        """Expired keys removed from a home."""
        self._purged.labels(home=home.value).inc(count)
