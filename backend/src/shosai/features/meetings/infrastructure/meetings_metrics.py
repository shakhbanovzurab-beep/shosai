"""Meetings' metrics of webhooks and the sweep (meetings plan §3.7).

`shosai_meetings_webhooks_total{kind}` counts verified webhooks by LiveKit's event, and
`shosai_meetings_sweep_rooms_total{verdict}` each open room the sweep looked at by its verdict
— `close` for the rooms it closed, `sfu_unreachable` for passes that closed nothing.
"""

from prometheus_client import CollectorRegistry, Counter

from shosai.features.meetings.application.video_server import WebhookKind
from shosai.features.meetings.domain.idle import SweepVerdict


class MeetingsMetrics:
    """Webhooks and the sweep, in the process's registry."""

    def __init__(self, registry: CollectorRegistry) -> None:
        self._webhooks = Counter(
            "shosai_meetings_webhooks",
            "Проверенные вебхуки LiveKit по событию",
            ("kind",),
            registry=registry,
        )
        self._sweep = Counter(
            "shosai_meetings_sweep_rooms",
            "Открытые комнаты, которые обошёл обход, по вердикту",
            ("verdict",),
            registry=registry,
        )

    def received(self, kind: WebhookKind) -> None:
        """One verified webhook of this kind."""
        self._webhooks.labels(kind=kind.value).inc()

    def swept(self, verdict: SweepVerdict) -> None:
        """The sweep's verdict on one open room."""
        self._sweep.labels(verdict=verdict.value).inc()
