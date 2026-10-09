"""Client spans of the statements: one per statement, no values, the error without its text."""

import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
import sqlalchemy as sa
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind, StatusCode
from sqlalchemy import exc

from shosai.core.db.tracing import operation_name
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.observability.span_privacy import PrivateAttributesSampler
from tests.harness.database_access import (
    DatabaseAccess,
    ProcessShape,
    open_database_access,
    slot_urls,
)
from tests.harness.run_slot import RunSlot

SECRET_NOTE = "a-value-that-must-not-reach-a-span"


@pytest_asyncio.fixture
async def traced(
    run_slot: RunSlot,
) -> AsyncIterator[tuple[InMemorySpanExporter, TracerProvider, DatabaseAccess]]:
    exporter = InMemorySpanExporter()
    provider = TracerProvider(sampler=PrivateAttributesSampler(), shutdown_on_exit=False)
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    shape = ProcessShape(tracer_provider=provider)
    async with open_database_access(slot_urls(run_slot), shape) as access:
        await access.gate.verify_at_start()
        exporter.clear()
        yield exporter, provider, access
    provider.shutdown()


async def test_each_statement_is_a_client_span_under_the_current_one(
    traced: tuple[InMemorySpanExporter, TracerProvider, DatabaseAccess],
) -> None:
    exporter, provider, access = traced
    scope = TenancyScope(Home.RU, user_id=uuid.uuid4())

    with provider.get_tracer("tests").start_as_current_span("request") as request:
        async with access.transactions.begin(scope, read_only=True) as session:
            await session.execute(sa.text("SELECT :note AS note"), {"note": SECRET_NOTE})

    statements = [span for span in exporter.get_finished_spans() if span.name != "request"]
    assert [span.name for span in statements] == ["SELECT", "SELECT"]
    for span in statements:
        attributes = dict(span.attributes or {})
        assert span.kind is SpanKind.CLIENT
        assert span.parent is not None
        assert span.parent.span_id == request.get_span_context().span_id
        assert attributes["db.system.name"] == "postgresql"
        assert attributes["shosai.home"] == "ru"
        assert str(attributes["db.namespace"]).startswith("shosai_test_")
        assert SECRET_NOTE not in str(attributes)
        assert str(scope.user_id) not in str(attributes)


async def test_a_failed_statement_has_its_type_and_sqlstate_but_not_its_message(
    traced: tuple[InMemorySpanExporter, TracerProvider, DatabaseAccess],
) -> None:
    exporter, _provider, access = traced

    with pytest.raises(exc.DataError):
        async with access.transactions.begin(TenancyScope(Home.EU)) as session:
            await session.execute(sa.text("SELECT CAST(:note AS integer)"), {"note": SECRET_NOTE})

    [failed] = [span for span in exporter.get_finished_spans() if "CAST" in str(span.attributes)]
    attributes = dict(failed.attributes or {})
    assert failed.status.status_code is StatusCode.ERROR
    assert failed.status.description is None
    assert attributes["db.response.status_code"] == "22P02"
    assert attributes["error.type"] == "InvalidTextRepresentation"
    assert SECRET_NOTE not in str(attributes)
    assert not failed.events


@pytest.mark.parametrize(
    ("statement", "operation"),
    [
        ("SELECT 1", "SELECT"),
        ("  insert into t values (1)", "INSERT"),
        ("WITH x AS (SELECT 1) SELECT * FROM x", "WITH"),
        ("\n\t", "QUERY"),
        ("/* comment */ SELECT 1", "QUERY"),
    ],
)
def test_the_operation_is_the_first_keyword(statement: str, operation: str) -> None:
    assert operation_name(statement) == operation
