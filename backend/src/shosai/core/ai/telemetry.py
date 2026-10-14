"""Each call a provider received: counted, timed and traced (F6 §3.11, §16.5).

A watch starts when an attempt of the route is sent and ends with its outcome — `ok`, the
`AiFailure` code, or `interrupted` when the caller went away. It feeds
`shosai_ai_calls_total` and `shosai_ai_call_duration_seconds` by provider, kind, call
class and outcome, and for streams `shosai_ai_time_to_first_piece_seconds`. Its span
`ai.call` carries the provider, kind, model, class and outcome only: no prompt, text,
audio or address, and no exception, whose message may quote the provider's answer (§16.8).
"""

import time
from typing import Final

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.semconv.attributes import error_attributes
from opentelemetry.trace import Span, SpanKind, Status, StatusCode
from prometheus_client import CollectorRegistry, Counter, Histogram

from shosai.core.ai.recording import MeteredCall

OK: Final = "ok"
INTERRUPTED: Final = "interrupted"
# Ответ модели — от сотен миллисекунд до двух минут анализа (§4.3).
DURATION_BUCKETS: Final = (0.25, 0.5, 1, 2, 4, 8, 15, 30, 60, 120)
FIRST_PIECE_BUCKETS: Final = (0.1, 0.25, 0.5, 1, 2, 4, 8, 15)
TRACER_NAME: Final = "shosai.ai"


class CallWatch:
    """One attempt in flight: its clock and its span."""

    def __init__(self, telemetry: CallTelemetry, call: MeteredCall, span: Span) -> None:
        self._telemetry = telemetry
        self._call = call
        self._span = span
        self._started = time.perf_counter()
        self._ended = False

    def first_piece(self) -> None:
        """The first piece of a stream arrived."""
        self._telemetry.first_piece(self._call, time.perf_counter() - self._started)

    def end(self, outcome: str) -> None:
        """Count and close the attempt once; later calls change nothing."""
        if self._ended:
            return
        self._ended = True
        self._telemetry.ended(self._call, outcome, time.perf_counter() - self._started)
        self._span.set_attribute("ai.outcome", outcome)
        if outcome != OK:
            self._span.set_attribute(error_attributes.ERROR_TYPE, outcome)
            self._span.set_status(Status(StatusCode.ERROR))
        self._span.end()


class CallTelemetry:
    """The metrics and the tracer of provider calls."""

    def __init__(self, registry: CollectorRegistry, tracer_provider: TracerProvider) -> None:
        self._tracer = tracer_provider.get_tracer(TRACER_NAME)
        labels = ("provider", "kind", "call_class", "outcome")
        self._calls = Counter(
            "shosai_ai_calls",
            "Вызовы, отправленные провайдеру, по виду, классу и исходу",
            labels,
            registry=registry,
        )
        self._duration = Histogram(
            "shosai_ai_call_duration_seconds",
            "Длительность вызова провайдера; у потока — до последнего куска",
            labels,
            buckets=DURATION_BUCKETS,
            registry=registry,
        )
        self._first_piece = Histogram(
            "shosai_ai_time_to_first_piece_seconds",
            "Время до первого куска потока ответа",
            ("provider", "kind"),
            buckets=FIRST_PIECE_BUCKETS,
            registry=registry,
        )

    def start(self, call: MeteredCall) -> CallWatch:
        """Start watching an attempt sent to the call's model."""
        span = self._tracer.start_span(
            "ai.call",
            kind=SpanKind.CLIENT,
            attributes={
                "ai.provider": call.model.provider.value,
                "ai.model": call.model.model,
                "ai.kind": call.kind,
                "ai.call_class": call.context.call_class.value,
            },
            record_exception=False,
            set_status_on_exception=False,
        )
        return CallWatch(self, call, span)

    def first_piece(self, call: MeteredCall, seconds: float) -> None:
        """Observe the time to a stream's first piece."""
        self._first_piece.labels(provider=call.model.provider.value, kind=call.kind).observe(
            seconds
        )

    def ended(self, call: MeteredCall, outcome: str, seconds: float) -> None:
        """Count an attempt and observe how long it took."""
        labels = {
            "provider": call.model.provider.value,
            "kind": call.kind,
            "call_class": call.context.call_class.value,
            "outcome": outcome,
        }
        self._calls.labels(**labels).inc()
        self._duration.labels(**labels).observe(seconds)
