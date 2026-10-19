"""The post-meeting pipeline's metrics (§16.3, §16.6).

`shosai_meetings_runs_total{source, outcome}` counts runs by their end; the post-meeting
objective's failures are the `failed` ones. `shosai_meetings_notes_ready_seconds{source}`
measures a run from its creation — the meeting's end — to its notes, for the objective of
notes within 10 minutes. `shosai_meetings_stage_seconds{stage, outcome}` times each stage
attempt. `shosai_meetings_oldest_open_run_seconds{home}` holds the age of the oldest
unfinished run, a ticket past 10 minutes.
"""

from typing import Final

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

from shosai.core.kernel.homes import Home
from shosai.features.meetings.domain.runs import RunSource, RunState, Stage

RUNS: Final = "shosai_meetings_runs_total"
NOTES_READY: Final = "shosai_meetings_notes_ready_seconds"
OLDEST_OPEN_RUN: Final = "shosai_meetings_oldest_open_run_seconds"
# Границы корзин: 600 — цель «заметки за 10 минут» (§16.3), остальные — для панели.
NOTES_BUCKETS: Final = (30, 60, 120, 300, 600, 900, 1800, 3600)
STAGE_BUCKETS: Final = (1, 5, 15, 30, 60, 120, 300, 600, 900)


class PipelineMetrics:
    """The pipeline's counters, histograms and gauge, in the process's registry."""

    def __init__(self, registry: CollectorRegistry) -> None:
        self._runs = Counter(
            RUNS.removesuffix("_total"),
            "Прогоны после встречи по источнику и исходу",
            ("source", "outcome"),
            registry=registry,
        )
        self._notes = Histogram(
            NOTES_READY,
            "Время от создания прогона — конца встречи — до готовых заметок",
            ("source",),
            buckets=NOTES_BUCKETS,
            registry=registry,
        )
        self._stages = Histogram(
            "shosai_meetings_stage_seconds",
            "Длительность попытки стадии прогона по стадии и исходу",
            ("stage", "outcome"),
            buckets=STAGE_BUCKETS,
            registry=registry,
        )
        self._oldest = Gauge(
            OLDEST_OPEN_RUN,
            "Возраст самого старого незаконченного прогона в доме",
            ("home",),
            registry=registry,
        )

    def finished(self, source: RunSource, state: RunState, seconds: float) -> None:
        """A run reached its end `seconds` after it was created."""
        self._runs.labels(source=source.value, outcome=state.value).inc()
        if state is not RunState.FAILED:
            self._notes.labels(source=source.value).observe(seconds)

    def attempt(self, stage: Stage, outcome: str, seconds: float) -> None:
        """One attempt of a stage ended: `done`, `retry` or `failed`."""
        self._stages.labels(stage=stage.value, outcome=outcome).observe(seconds)

    def oldest_open(self, home: Home, seconds: float) -> None:
        """The age of the home's oldest unfinished run, zero without one."""
        self._oldest.labels(home=home.value).set(seconds)
