"""The live transcript's metrics and the monitors of inv-6 and inv-7 (§16.4).

`shosai_notes_transcript_lines_total{outcome}` counts the drained lines stored,
replayed, refused (a meeting gone or not kept), cut to the line's cap, or failed with
their batch. `shosai_notes_transcript_lines_missing_total` counts lines capture showed
that a settled meeting does not hold: inv-6 breaks at its first increase.
`shosai_notes_unsettled{home}` holds the ended meetings older than a quarter of an hour
that no sweep settled yet: a spoken meeting among them may still have no run (inv-7).
"""

from enum import StrEnum
from typing import Final

from prometheus_client import CollectorRegistry, Counter, Gauge

from shosai.core.kernel.homes import Home

LINES_MISSING: Final = "shosai_notes_transcript_lines_missing_total"
UNSETTLED: Final = "shosai_notes_unsettled"


class LineOutcome(StrEnum):
    """What happened to a drained line."""

    STORED = "stored"
    REPLAYED = "replayed"
    REFUSED = "refused"
    CUT = "cut"
    FAILED = "failed"


class TranscriptMetrics:
    """The drain's counters and the settling's monitors, in the process's registry."""

    def __init__(self, registry: CollectorRegistry) -> None:
        self._lines = Counter(
            "shosai_notes_transcript_lines",
            "Строки живой расшифровки из очереди: сохранены, повторы, отказ, обрезаны, сбой",
            ("outcome",),
            registry=registry,
        )
        self._missing = Counter(
            LINES_MISSING.removesuffix("_total"),
            "Строки, которые capture показал, а закрытая встреча не хранит (inv-6)",
            registry=registry,
        )
        self._unsettled = Gauge(
            UNSETTLED,
            "Закончившиеся встречи старше четверти часа, которые обход ещё не досчитал",
            ("home",),
            registry=registry,
        )

    def lines(self, outcome: LineOutcome, count: int) -> None:
        """Count `count` lines of this outcome."""
        if count:
            self._lines.labels(outcome=outcome.value).inc(count)

    def missing(self, count: int) -> None:
        """Lines shown and not stored, found at a meeting's settling."""
        if count:
            self._missing.inc(count)

    def unsettled(self, home: Home, count: int) -> None:
        """The home's ended meetings still not settled after their grace."""
        self._unsettled.labels(home=home.value).set(count)
