"""Memory in numbers (Leo §11.3, memory plan §3.8): closed labels, no ids, no statements.

`shosai_memory_recall_total{outcome}` counts every recall a turn asked for — facts given,
nothing to give, late, memory off, no consent, failed — and `shosai_memory_recall_seconds` how
long it took; `shosai_memory_recall_facts` how many facts reached the turn. The embedding pass
counts the facts it gave vectors to and those it could not (`shosai_memory_embedded_total`).
"""

from enum import StrEnum
from typing import Final

from prometheus_client import CollectorRegistry, Counter, Histogram

RECALL_SECONDS: Final = "shosai_memory_recall_seconds"
RECALL_BUCKETS: Final = (0.01, 0.025, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.5, 1)


class RecallOutcome(StrEnum):
    """How a recall ended."""

    HIT = "hit"
    EMPTY = "empty"
    LATE = "late"
    OFF = "off"
    NO_CONSENT = "no_consent"
    FAILED = "failed"


class EmbedOutcome(StrEnum):
    """What the embedding pass did with a fact."""

    EMBEDDED = "embedded"
    NO_CONSENT = "no_consent"
    FAILED = "failed"


class MemoryMetrics:
    """Memory's counters and times, in the process's registry."""

    def __init__(self, registry: CollectorRegistry) -> None:
        self._recalls = Counter(
            "shosai_memory_recall",
            "Вспоминания для хода по исходу",
            ("outcome",),
            registry=registry,
        )
        self._seconds = Histogram(
            RECALL_SECONDS,
            "Сколько длилось вспоминание для хода",
            buckets=RECALL_BUCKETS,
            registry=registry,
        )
        self._facts = Histogram(
            "shosai_memory_recall_facts",
            "Сколько фактов вспоминание дало ходу",
            buckets=(0, 1, 2, 4, 6, 8, 10, 12),
            registry=registry,
        )
        self._embedded = Counter(
            "shosai_memory_embedded",
            "Факты, которым проход эмбеддингов дал вектор или не смог",
            ("outcome",),
            registry=registry,
        )

    def recalled(self, outcome: RecallOutcome, seconds: float, facts: int) -> None:
        """One recall: how it ended, its time and how many facts it gave."""
        self._recalls.labels(outcome.value).inc()
        self._seconds.observe(seconds)
        self._facts.observe(facts)

    def embedded(self, outcome: EmbedOutcome, facts: int) -> None:
        """Facts the embedding pass handled one way."""
        self._embedded.labels(outcome.value).inc(facts)
