"""Meetings' metrics of webhooks, the sweep and recordings (meetings plan §3.7).

`shosai_meetings_webhooks_total{kind}` counts verified webhooks by LiveKit's event,
`shosai_meetings_sweep_rooms_total{verdict}` each open room the sweep looked at by its verdict
— `close` for the rooms it closed, `sfu_unreachable` for passes that closed nothing — and
`shosai_meetings_recordings_total{outcome}` each recording that ended, once: `complete`, or
the failure's code (`start_refused`, `egress_failed`, `egress_aborted`, `egress_lost`).
"""

from prometheus_client import CollectorRegistry, Counter

from shosai.features.meetings.application.video_server import WebhookKind
from shosai.features.meetings.domain.idle import SweepVerdict
from shosai.features.meetings.domain.recordings import RecordingFailure

# Исход записи без сбоя; остальные исходы — коды RecordingFailure.
COMPLETE_OUTCOME = "complete"


class MeetingsMetrics:
    """Webhooks, the sweep and recordings, in the process's registry."""

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
        self._recordings = Counter(
            "shosai_meetings_recordings",
            "Записи звонков, дошедшие до конца, по исходу",
            ("outcome",),
            registry=registry,
        )

    def recording_ended(self, failure: RecordingFailure | None) -> None:
        """One recording ended: complete when `failure` is None, otherwise failed with it."""
        outcome = COMPLETE_OUTCOME if failure is None else failure.value
        self._recordings.labels(outcome=outcome).inc()

    def received(self, kind: WebhookKind) -> None:
        """One verified webhook of this kind."""
        self._webhooks.labels(kind=kind.value).inc()

    def swept(self, verdict: SweepVerdict) -> None:
        """The sweep's verdict on one open room."""
        self._sweep.labels(verdict=verdict.value).inc()
