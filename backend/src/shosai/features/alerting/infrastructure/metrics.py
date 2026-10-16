"""Metrics of the alerting slice; labels from closed sets: an event type, three outcomes."""

from typing import Literal

from prometheus_client import CollectorRegistry, Counter

type PostOutcome = Literal["accepted", "unavailable", "rejected"]


class AlertingMetrics:
    """Alerts handed to Alertmanager by kind and outcome."""

    def __init__(self, registry: CollectorRegistry) -> None:
        self._posts = Counter(
            "shosai_alerting_posts",
            "Передачи оповещений о бизнес-событиях в Alertmanager по виду и исходу",
            ("kind", "outcome"),
            registry=registry,
        )

    def posted(self, kind: str, outcome: PostOutcome) -> None:
        """One attempt to hand an alert over."""
        self._posts.labels(kind=kind, outcome=outcome).inc()
