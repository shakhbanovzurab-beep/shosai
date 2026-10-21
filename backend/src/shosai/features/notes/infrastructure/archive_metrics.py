"""What the transcript archive did (§16): meetings archived or refused, partitions dropped.

`shosai_notes_transcripts_archived_total{home, outcome}` counts meetings: `archived` when the
object read back matched the lines and the pointer was set, `mismatch` when it did not or a
line arrived meanwhile — the meeting is tried again on the next pass.
`shosai_notes_transcript_partitions_dropped_total{home}` counts the months whose partition
went after every meeting in it was archived.
"""

from enum import StrEnum

from prometheus_client import CollectorRegistry, Counter

from shosai.core.kernel.homes import Home


class ArchiveOutcome(StrEnum):
    """What came of one meeting's archiving."""

    ARCHIVED = "archived"
    MISMATCH = "mismatch"


class ArchiveMetrics:
    """The archive's counters in the process's registry."""

    def __init__(self, registry: CollectorRegistry) -> None:
        self._meetings = Counter(
            "shosai_notes_transcripts_archived",
            "Расшифровки встреч, ушедшие в архив бакета, и несовпадения при сверке",
            ("home", "outcome"),
            registry=registry,
        )
        self._dropped = Counter(
            "shosai_notes_transcript_partitions_dropped",
            "Месячные партиции расшифровок, удалённые после архива всех их встреч",
            ("home",),
            registry=registry,
        )

    def archived(self, home: Home, outcome: ArchiveOutcome) -> None:
        """One meeting archived, or refused for a mismatch."""
        self._meetings.labels(home=home.value, outcome=outcome.value).inc()

    def dropped(self, home: Home) -> None:
        """One month's partition gone."""
        self._dropped.labels(home=home.value).inc()
