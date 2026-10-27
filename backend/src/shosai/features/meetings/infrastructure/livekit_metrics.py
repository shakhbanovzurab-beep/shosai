"""Meetings' metrics of the SFU (meetings plan §3.7).

`shosai_meetings_livekit_requests_total{operation, outcome}` and
`shosai_meetings_livekit_request_seconds{operation}` count and time every call to LiveKit's
server API — `ok`, `unreachable`, `server_error` or `refused`;
`shosai_meetings_webhook_verifications_total{outcome}` counts webhooks accepted and rejected,
for the alert on more than 1 % failing verification.
"""

from prometheus_client import CollectorRegistry, Counter, Histogram

# Вызовы API LiveKit — десятки миллисекунд; таймаут вызова — 5 с.
LATENCY_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)


class LiveKitMetrics:
    """Calls to the SFU and webhook verifications, in the process's registry."""

    def __init__(self, registry: CollectorRegistry) -> None:
        self._requests = Counter(
            "shosai_meetings_livekit_requests",
            "Вызовы серверного API LiveKit по операции и исходу",
            ("operation", "outcome"),
            registry=registry,
        )
        self._latency = Histogram(
            "shosai_meetings_livekit_request_seconds",
            "Длительность вызова серверного API LiveKit",
            ("operation",),
            buckets=LATENCY_BUCKETS,
            registry=registry,
        )
        self._webhooks = Counter(
            "shosai_meetings_webhook_verifications",
            "Проверки подписи вебхуков LiveKit: принят или отклонён",
            ("outcome",),
            registry=registry,
        )

    def called(self, operation: str, outcome: str, seconds: float) -> None:
        """One call to the SFU ended with this outcome after this many seconds."""
        self._requests.labels(operation=operation, outcome=outcome).inc()
        self._latency.labels(operation=operation).observe(seconds)

    def webhook_verified(self, *, accepted: bool) -> None:
        """One webhook was accepted or rejected."""
        self._webhooks.labels(outcome="accepted" if accepted else "rejected").inc()
