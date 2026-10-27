"""Leo's voice conversations in Prometheus: how they end and how long they last.

The gateway already counts the sockets of `/v1/ws/voice` by close code; these say why a
conversation that opened ended — the person, a limit, the minutes, Gemini or a restart.
"""

from typing import Final

from prometheus_client import CollectorRegistry, Counter, Histogram

from shosai.features.capture.domain.voice import VoiceEnd

# Корзины длины разговора: от оборванного на первой фразе до получасового предела.
SECONDS_BUCKETS: Final = (5, 15, 30, 60, 120, 300, 600, 900, 1200, 1800, float("inf"))


class VoiceMetrics:
    """Conversations by their end and their length."""

    def __init__(self, registry: CollectorRegistry) -> None:
        self._ended = Counter(
            "shosai_capture_voice_conversations",
            "Leo's voice conversations that opened, by why they ended.",
            ("end",),
            registry=registry,
        )
        self._seconds = Histogram(
            "shosai_capture_voice_conversation_seconds",
            "Length of a voice conversation that opened.",
            buckets=SECONDS_BUCKETS,
            registry=registry,
        )
        for end in VoiceEnd:
            self._ended.labels(end=end.value)

    def ended(self, end: VoiceEnd, seconds: float) -> None:
        """A conversation ended."""
        self._ended.labels(end=end.value).inc()
        self._seconds.observe(seconds)
