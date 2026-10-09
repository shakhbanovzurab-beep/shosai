"""A delivery continues the trace and the request of the unit of work that wrote the event."""

import uuid
from collections.abc import Iterator

import pytest
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind
from redis.asyncio import Redis

from shosai.core.events.system import RELAY_OUTBOX
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.observability.log_context import log_context
from shosai.core.observability.span_privacy import PrivateAttributesSampler
from shosai.core.tasks.payloads import HomeTaskPayload
from shosai.core.tasks.queues import TaskQueue
from tests.core.events.bench import Applied, NoteState, NoteWritten, event_bench, recording, runs
from tests.core.observability.capture import captured_logs
from tests.core.tasks.workbench import eventually, running
from tests.harness.database_access import DatabaseAccess

INDEX = "search.index_note"


@pytest.fixture
def spans() -> Iterator[tuple[TracerProvider, InMemorySpanExporter]]:
    exporter = InMemorySpanExporter()
    provider = TracerProvider(sampler=PrivateAttributesSampler(), shutdown_on_exit=False)
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    yield provider, exporter
    provider.shutdown()


def named(exporter: InMemorySpanExporter, name: str) -> ReadableSpan:
    [span] = [span for span in exporter.get_finished_spans() if span.name == name]
    return span


@pytest.mark.usefixtures("probe_table")
async def test_the_delivery_joins_the_producers_trace_and_request(
    valkey: Redis, homes: DatabaseAccess, spans: tuple[TracerProvider, InMemorySpanExporter]
) -> None:
    provider, exporter = spans
    bench = event_bench(valkey, homes, [recording(INDEX, Applied())], tracer_provider=provider)
    tracer = provider.get_tracer("tests")

    with tracer.start_as_current_span("request") as request, log_context(request_id="req-9"):
        async with homes.transactions.begin(TenancyScope(Home.RU)) as session:
            event_id = await bench.outbox.add(
                session, NoteWritten(record_id=uuid.uuid4(), state=NoteState.DRAFT)
            )
    with captured_logs() as logs:
        async with running(bench.tasks.broker(TaskQueue.CRITICAL)), running(bench.tasks.broker()):
            await bench.tasks.system.sender.send_tick(
                RELAY_OUTBOX, HomeTaskPayload(home=Home.RU), Home.RU.value
            )
            await eventually(runs(bench, TaskQueue.DEFAULT, f"events.{INDEX}", "succeeded"))

    producer = request.get_span_context()
    publish = named(exporter, "publish probe.note.written")
    relay_run = named(exporter, f"task {RELAY_OUTBOX.name}")
    delivery = named(exporter, f"task events.{INDEX}")
    assert publish.kind is SpanKind.PRODUCER
    assert publish.parent is not None
    assert (publish.parent.trace_id, publish.parent.span_id) == (
        producer.trace_id,
        producer.span_id,
    )
    assert [link.context.span_id for link in publish.links] == [relay_run.context.span_id]
    assert publish.attributes == {
        "messaging.operation.type": "send",
        "messaging.message.id": str(event_id),
        "shosai.event.type": "probe.note.written",
    }
    assert delivery.parent is not None
    assert delivery.parent.span_id == publish.context.span_id
    assert delivery.context.trace_id == producer.trace_id
    [line] = [
        line
        for line in logs.lines()
        if line["message"] == "Задача выполнена" and line["task_name"] == f"events.{INDEX}"
    ]
    assert (line["request_id"], line["event_id"], line["home"]) == ("req-9", str(event_id), "ru")
