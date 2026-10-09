"""Trace and log context of an event while the relay passes it on (§14 rule 13, §16.2).

An event continues the trace of the unit of work that wrote it: the relay opens one
producer span per event as a child of the stored trace context, linked to the relay's
own run, and queues the deliveries inside it, so each delivery's consumer span joins the
producer's trace. The event's request id is bound meanwhile, so the deliveries' log
lines carry it too. The span holds ids and codes only; a failure, the error type (§16.8).
"""

from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID

from opentelemetry import trace
from opentelemetry.context import Context
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.trace import Link, SpanKind, Status, StatusCode
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from shosai.core.observability.log_context import log_context
from shosai.core.tasks.dead_letter import qualified_name

TRACER_NAME = "shosai.events"


class PublishSpans:
    """Opens the producer span of each event the relay passes on."""

    def __init__(self, tracer_provider: TracerProvider) -> None:
        self._tracer = tracer_provider.get_tracer(TRACER_NAME)
        self._propagator = TraceContextTextMapPropagator()

    def producer_context(self, traceparent: str | None) -> Context | None:
        """The stored trace context of the event, or None when it has no valid one."""
        if traceparent is None:
            return None
        context = self._propagator.extract({"traceparent": traceparent})
        span_context = trace.get_current_span(context).get_span_context()
        return context if span_context.is_valid else None

    @contextmanager
    def publishing(
        self, event_id: UUID, event_type: str, traceparent: str | None, request_id: str | None
    ) -> Iterator[None]:
        """The block where the event's deliveries are queued."""
        parent = self.producer_context(traceparent)
        run = trace.get_current_span().get_span_context()
        links = [Link(run)] if parent is not None and run.is_valid else []
        with self._tracer.start_as_current_span(
            f"publish {event_type}",
            context=parent,
            kind=SpanKind.PRODUCER,
            links=links,
            attributes={
                "messaging.operation.type": "send",
                "messaging.message.id": str(event_id),
                "shosai.event.type": event_type,
            },
            record_exception=False,
            set_status_on_exception=False,
        ) as span:
            try:
                if request_id is None:
                    yield
                else:
                    with log_context(request_id=request_id):
                        yield
            except Exception as error:
                span.set_attribute("error.type", qualified_name(error))
                span.set_status(Status(StatusCode.ERROR))
                raise
