"""The trace of the sender continues in the worker's run; spans carry no error text."""

from collections.abc import Iterator

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind, StatusCode
from redis.asyncio import Redis

from tests.core.tasks.workbench import Probe, Runs, declare, eventually, running, settled, workbench
from whisperer.core.observability.span_privacy import PrivateAttributesSampler
from whisperer.core.tasks.declaration import TaskHandler

SECRET_TEXT = "user@example.com was not found"


@pytest.fixture
def spans() -> Iterator[tuple[TracerProvider, InMemorySpanExporter]]:
    exporter = InMemorySpanExporter()
    provider = TracerProvider(sampler=PrivateAttributesSampler(), shutdown_on_exit=False)
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    yield provider, exporter
    provider.shutdown()


def run_span(exporter: InMemorySpanExporter, task: str) -> ReadableSpan:
    [span] = [span for span in exporter.get_finished_spans() if span.name == f"task {task}"]
    return span


async def test_the_run_continues_the_trace_of_the_sender(
    valkey: Redis, spans: tuple[TracerProvider, InMemorySpanExporter]
) -> None:
    provider, exporter = spans
    task = declare("probe.traced")
    seen: list[int] = []

    async def handle(_payload: Probe) -> None:
        seen.append(trace.get_current_span().get_span_context().trace_id)

    bench = workbench(valkey, [TaskHandler(task, handle)], tracer_provider=provider)
    tracer = provider.get_tracer("tests")

    async with running(bench.broker()):
        with tracer.start_as_current_span("request") as request:
            task_id = await bench.system.sender.send(task, Probe(note="след"))
        await eventually(settled(bench, task.name, "succeeded"))

    sender = request.get_span_context()
    run = run_span(exporter, task.name)
    assert run.context is not None
    assert run.context.trace_id == sender.trace_id
    assert run.parent is not None
    assert run.parent.span_id == sender.span_id
    assert run.kind is SpanKind.CONSUMER
    assert seen == [sender.trace_id]
    assert run.attributes == {
        "messaging.operation.type": "process",
        "messaging.destination.name": "default",
        "messaging.message.id": task_id,
        "whisperer.task.name": task.name,
    }


async def test_a_failed_run_is_marked_with_the_error_type_only(
    valkey: Redis, spans: tuple[TracerProvider, InMemorySpanExporter]
) -> None:
    provider, exporter = spans
    task = declare("probe.traced_failure")
    handler = Runs().handler(task, failure=LookupError(SECRET_TEXT))
    bench = workbench(valkey, [handler], tracer_provider=provider)

    async with running(bench.broker()):
        await bench.system.sender.send(task, Probe(note="x"))
        await eventually(settled(bench, task.name, "dead_lettered"))

    run = run_span(exporter, task.name)
    assert run.status.status_code is StatusCode.ERROR
    assert run.status.description is None
    assert run.attributes is not None
    assert run.attributes["error.type"] == "builtins.LookupError"
    assert run.events == ()
    assert SECRET_TEXT not in str(run.to_json())


async def test_a_task_sent_outside_a_trace_starts_its_own(
    valkey: Redis, spans: tuple[TracerProvider, InMemorySpanExporter]
) -> None:
    provider, exporter = spans
    task = declare("probe.untraced")
    bench = workbench(valkey, [Runs().handler(task)], tracer_provider=provider)

    async with running(bench.broker()):
        await bench.system.sender.send(task, Probe(note="без следа"))
        await eventually(settled(bench, task.name, "succeeded"))

    assert run_span(exporter, task.name).parent is None
