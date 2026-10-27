"""Memory in numbers (Leo §11.3, memory plan §3.8): closed labels, no ids, no statements.

`shosai_memory_recall_total{outcome}` counts every recall a turn asked for — facts given,
nothing to give, late, memory off, no consent, failed — and `shosai_memory_recall_seconds` how
long it took; `shosai_memory_recall_facts` how many facts reached the turn. The embedding pass
counts the facts it gave vectors to and those it could not (`shosai_memory_embedded_total`).
`shosai_memory_summary_writes_total{trigger, outcome}` counts the summary's writes: why — a
stale open, a refresh, a box message, the upkeep — and how they ended. The upkeep counts the
facts it expired, purged, erased with their source and brought back
(`shosai_memory_upkeep_facts_total{part}`); the hourly check sets the facts a writer created
after their person switched memory off (`shosai_memory_written_while_off{home}`, must stay 0).
A turn's or a meeting's extraction counts how its model call ended
(`shosai_memory_extractions_total{source, outcome}`); a turn's admission how long after the turn
it was written (`shosai_memory_admission_lag_seconds`); the person's answers to candidates —
remembered, turned down, expired unanswered — `shosai_memory_candidates_total{source, answer}`.
"""

from collections.abc import Sequence
from enum import StrEnum
from typing import Final

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

from shosai.core.kernel.homes import Home

RECALL_SECONDS: Final = "shosai_memory_recall_seconds"
RECALL_BUCKETS: Final = (0.01, 0.025, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.5, 1)
ADMISSION_LAG: Final = "shosai_memory_admission_lag_seconds"
# Минута — граница тикета задержки приёма (план §3.8): строка под ответом ждёт его.
LAG_BUCKETS: Final = (1, 2, 5, 10, 15, 20, 30, 45, 60, 90, 120, 300, 600)
EXTRACTIONS: Final = "shosai_memory_extractions_total"
CANDIDATES: Final = "shosai_memory_candidates_total"


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


class SummaryTrigger(StrEnum):
    """Why the summary is written."""

    OPEN = "open"
    REFRESH = "refresh"
    BOX = "box"
    UPKEEP = "upkeep"


class CandidateAnswer(StrEnum):
    """What became of a candidate."""

    ACCEPTED = "accepted"
    TURNED_DOWN = "turned_down"
    EXPIRED = "expired"


class UpkeepPart(StrEnum):
    """What the upkeep did to facts."""

    EXPIRED = "expired"
    PURGED = "purged"
    ERASED = "erased"
    RESTORED = "restored"


ADMISSIONS: Final = "shosai_memory_admissions_total"
WRITTEN_WHILE_OFF: Final = "shosai_memory_written_while_off"


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
        self._admissions = Counter(
            ADMISSIONS.removesuffix("_total"),
            "Утверждения, найденные в ходе или встрече, по тому, чем они стали",
            ("source", "outcome"),
            registry=registry,
        )
        self._summaries = Counter(
            "shosai_memory_summary_writes",
            "Записи сводки памяти по поводу и исходу",
            ("trigger", "outcome"),
            registry=registry,
        )
        self._lag = Histogram(
            ADMISSION_LAG,
            "Сколько прошло от конца хода до записи его утверждений в память",
            buckets=LAG_BUCKETS,
            registry=registry,
        )
        self._extractions = Counter(
            EXTRACTIONS.removesuffix("_total"),
            "Извлечения утверждений из хода или встречи по исходу вызова модели",
            ("source", "outcome"),
            registry=registry,
        )
        self._candidates = Counter(
            CANDIDATES.removesuffix("_total"),
            "Ответы человека на кандидатов памяти по источнику",
            ("source", "answer"),
            registry=registry,
        )
        self._upkeep = Counter(
            "shosai_memory_upkeep_facts",
            "Факты, которые уход за памятью завершил, вычистил, стёр с источником или вернул",
            ("part",),
            registry=registry,
        )
        self._while_off = Gauge(
            WRITTEN_WHILE_OFF,
            "Факты, записанные после выключения памяти человеком, по дому; должно быть 0",
            ("home",),
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

    def summary_written(self, trigger: SummaryTrigger, outcome: str) -> None:
        """One write of a summary: why and how it ended."""
        self._summaries.labels(trigger.value, outcome).inc()

    def admission_lag(self, seconds: float) -> None:
        """How long after its turn an admission was written."""
        self._lag.observe(max(seconds, 0.0))

    def extracted(self, source: str, *, ok: bool) -> None:
        """One extraction's model call: answered, or failed and retried later."""
        self._extractions.labels(source, "ok" if ok else "failed").inc()

    def answered(self, source: str, answer: CandidateAnswer, candidates: int = 1) -> None:
        """Candidates of one source the person answered one way, or that expired."""
        if candidates:
            self._candidates.labels(source, answer.value).inc(candidates)

    def upkept(self, part: UpkeepPart, facts: int) -> None:
        """Facts the upkeep handled one way."""
        if facts:
            self._upkeep.labels(part.value).inc(facts)

    def written_while_off(self, home: Home, facts: int) -> None:
        """The hourly check's count of one home."""
        self._while_off.labels(home.value).set(facts)

    def embedded(self, outcome: EmbedOutcome, facts: int) -> None:
        """Facts the embedding pass handled one way."""
        self._embedded.labels(outcome.value).inc(facts)

    def admitted(self, source: str, outcomes: Sequence[StrEnum]) -> None:
        """What the statements of one turn or meeting became; `none` when there were none."""
        if not outcomes:
            self._admissions.labels(source, "none").inc()
        for outcome in outcomes:
            self._admissions.labels(source, outcome.value).inc()
