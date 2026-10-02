"""Trace context across the queue: send → run (target architecture §14 rule 13, §16.2).

The sender puts the W3C trace context of its current span into the message's labels; the
worker continues that trace with one consumer span per run, named by the task. The span
carries ids and codes only: on failure, the error's type, never its message (§16.8).
TaskIQ's own OpenTelemetry middleware is not used — it records the exception's text and
needs a process-metrics library this backend has no use for (F1 plan, choice F1-C13).
"""

from contextvars import Token
from typing import Any

from opentelemetry import context, trace
from opentelemetry.context import Context
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.trace import Span, SpanKind, Status, StatusCode
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from taskiq import TaskiqMessage, TaskiqMiddleware, TaskiqResult

from whisperer.core.tasks.dead_letter import qualified_name
from whisperer.core.tasks.queues import TaskQueue

TRACER_NAME = "whisperer.tasks"


class TaskTracing(TaskiqMiddleware):
    """Carries the trace context into a message and continues it in the run."""

    def __init__(self, tracer_provider: TracerProvider, queue: TaskQueue) -> None:
        super().__init__()
        self._tracer = tracer_provider.get_tracer(TRACER_NAME)
        self._propagator = TraceContextTextMapPropagator()
        self._queue = queue
        self._runs: dict[str, tuple[Span, Token[Context]]] = {}

    def pre_send(self, message: TaskiqMessage) -> TaskiqMessage:
        """Put the sender's trace context into the labels."""
        self._propagator.inject(message.labels)
        return message

    def pre_execute(self, message: TaskiqMessage) -> TaskiqMessage:
        """Start the run's span as a child of the sender's span and make it current."""
        parent = self._propagator.extract(message.labels)
        span = self._tracer.start_span(
            f"task {message.task_name}",
            context=parent,
            kind=SpanKind.CONSUMER,
            attributes={
                "messaging.operation.type": "process",
                "messaging.destination.name": self._queue.value,
                "messaging.message.id": message.task_id,
                "whisperer.task.name": message.task_name,
            },
        )
        token = context.attach(trace.set_span_in_context(span))
        self._runs[message.task_id] = (span, token)
        return message

    def post_execute(self, message: TaskiqMessage, result: TaskiqResult[Any]) -> None:
        """End the run's span; a failure is marked with the error's type only."""
        run = self._runs.pop(message.task_id, None)
        if run is None:
            return
        span, token = run
        if result.is_err and result.error is not None:
            span.set_attribute("error.type", qualified_name(result.error))
            span.set_status(Status(StatusCode.ERROR))
        span.end()
        context.detach(token)
