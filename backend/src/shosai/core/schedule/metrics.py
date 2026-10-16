"""Metrics of periodic jobs: what each tick did and when each job was last queued (§16.4).

Labels come from closed sets: `schedule` — a job declared in code, one of two homes, one
of three outcomes. Lateness is read as now minus
`shosai_periodic_job_last_queued_timestamp_seconds` against the job's interval. The label
is not `job`: Prometheus gives every scraped series a `job` of its own, and a metric's
`job` would arrive renamed `exported_job`.
"""

import time
from typing import Literal

from prometheus_client import CollectorRegistry, Counter, Gauge

from shosai.core.kernel.homes import Home

type JobOutcome = Literal["queued", "skipped", "failed"]


class ScheduleMetrics:
    """Claimed job runs by outcome, and the last time each job was queued."""

    def __init__(self, registry: CollectorRegistry) -> None:
        self._runs = Counter(
            "shosai_periodic_job_runs",
            "Захваченные запуски периодических задач: поставлен, пропущен, не поставлен",
            ("schedule", "home", "outcome"),
            registry=registry,
        )
        self._last_queued = Gauge(
            "shosai_periodic_job_last_queued_timestamp_seconds",
            "Unix-время, когда периодическая задача последний раз поставлена в очередь",
            ("schedule", "home"),
            registry=registry,
        )

    def count(self, job: str, home: Home, outcome: JobOutcome) -> None:
        """One claimed run of a job in a home."""
        self._runs.labels(schedule=job, home=home.value, outcome=outcome).inc()
        if outcome == "queued":
            self._last_queued.labels(schedule=job, home=home.value).set(time.time())
