"""Meetings' lifecycle metrics (§16.1): meetings started and how they ended.

`shosai_meetings_started_total{source}` counts meetings started; `shosai_meetings_ended_total
{source, cause}` counts their ends by the client, by silence, at the ceiling or by a new
meeting on the same device. Labels are bounded enums; no meeting, person or title is one.
"""

from prometheus_client import CollectorRegistry, Counter

from shosai.features.meetings.domain.meetings import EndCause, MeetingSource


class MeetingMetrics:
    """The lifecycle counters, in the process's registry."""

    def __init__(self, registry: CollectorRegistry) -> None:
        self._started = Counter(
            "shosai_meetings_started",
            "Начатые встречи по источнику",
            ("source",),
            registry=registry,
        )
        self._ended = Counter(
            "shosai_meetings_ended",
            "Закончившиеся встречи по источнику и причине конца",
            ("source", "cause"),
            registry=registry,
        )

    def started(self, source: MeetingSource) -> None:
        """A meeting started."""
        self._started.labels(source=source.value).inc()

    def ended(self, source: MeetingSource, cause: EndCause) -> None:
        """A meeting ended for this cause."""
        self._ended.labels(source=source.value, cause=cause.value).inc()
