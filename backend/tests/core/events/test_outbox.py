"""An event exists exactly when its effect does, with the tenancy and trace of its transaction."""

import uuid

import psycopg
import pytest
import sqlalchemy as sa
from opentelemetry.sdk.trace import TracerProvider
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import NotAHomeTransactionError, transaction_info
from shosai.core.events.catalog import EventCatalog
from shosai.core.events.outbox import (
    EventOutbox,
    ReadOnlyEventTransactionError,
    UnlistedEventError,
)
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.observability.log_context import log_context
from tests.core.events.bench import NoteArchived, NoteState, NoteWritten, event_bench
from tests.harness.connections import fetch_rows, fetch_value
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot

USER_ID = uuid.UUID("0190f0f0-0000-7000-8000-000000000001")
ORG_ID = uuid.UUID("0190f0f0-0000-7000-8000-000000000002")


class EffectFailedError(Exception):
    """The effect of the transaction failed after the event was written."""


@pytest.mark.parametrize("home", list(Home))
async def test_an_event_is_stored_in_its_home_with_the_scope_trace_and_request_of_its_effect(
    valkey: Redis, homes: DatabaseAccess, run_slot: RunSlot, home: Home
) -> None:
    bench = event_bench(valkey, homes)
    record_id = uuid.uuid4()
    tracer = TracerProvider().get_tracer("tests")

    with tracer.start_as_current_span("request") as span, log_context(request_id="req-7"):
        async with homes.transactions.begin(TenancyScope(home, USER_ID, ORG_ID)) as session:
            event_id = await bench.outbox.add(
                session, NoteWritten(record_id=record_id, state=NoteState.FINAL, reason="manual")
            )
            started = await session.scalar(sa.select(sa.func.now()))

    connection = run_slot.claimed.connections[home]
    [row] = await fetch_rows(connection, "SELECT * FROM outbox_messages")
    trace_id = format(span.get_span_context().trace_id, "032x")
    assert row["id"] == event_id
    assert event_id.version == 7
    assert (row["event_type"], row["version"]) == ("probe.note.written", 1)
    assert row["payload"] == {"record_id": str(record_id), "state": "final", "reason": "manual"}
    assert (row["user_id"], row["org_id"]) == (USER_ID, ORG_ID)
    assert row["traceparent"].split("-")[1] == trace_id
    assert row["request_id"] == "req-7"
    assert row["occurred_at"] == started
    assert (row["attempts"], row["published_at"]) == (0, None)
    other = run_slot.claimed.connections[Home.EU if home is Home.RU else Home.RU]
    assert await fetch_value(other, "SELECT count(*) FROM outbox_messages") == 0


async def test_a_rolled_back_effect_leaves_no_event(
    valkey: Redis, homes: DatabaseAccess, probe_table: sa.TableClause, run_slot: RunSlot
) -> None:
    bench = event_bench(valkey, homes)

    async def write_effect_that_fails() -> None:
        record_id = uuid.uuid4()
        async with homes.transactions.begin(TenancyScope(Home.RU)) as session:
            await session.execute(sa.insert(probe_table).values(id=record_id, note="effect"))
            await bench.outbox.add(session, NoteWritten(record_id=record_id, state=NoteState.DRAFT))
            raise EffectFailedError

    with pytest.raises(EffectFailedError):
        await write_effect_that_fails()

    connection = run_slot.claimed.connections[Home.RU]
    assert await fetch_value(connection, "SELECT count(*) FROM outbox_messages") == 0
    assert await fetch_value(connection, "SELECT count(*) FROM probe_records") == 0


async def test_an_event_without_a_listed_class_or_an_effect_is_refused(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    outbox = EventOutbox(EventCatalog([NoteWritten], []))
    archived = NoteArchived(record_id=uuid.uuid4())
    written = NoteWritten(record_id=uuid.uuid4(), state=NoteState.DRAFT)

    async with homes.transactions.begin(TenancyScope(Home.EU)) as session:
        with pytest.raises(UnlistedEventError, match=r"probe\.note\.archived"):
            await outbox.add(session, archived)
    async with homes.transactions.begin(TenancyScope(Home.EU), read_only=True) as session:
        with pytest.raises(ReadOnlyEventTransactionError):
            await outbox.add(session, written)

    connection = run_slot.claimed.connections[Home.EU]
    assert await fetch_value(connection, "SELECT count(*) FROM outbox_messages") == 0


async def test_only_a_home_transaction_knows_its_scope(homes: DatabaseAccess) -> None:
    scope = TenancyScope(Home.RU, USER_ID)
    outbox = EventOutbox(EventCatalog([NoteWritten], []))

    async with homes.transactions.begin(scope, read_only=True) as session:
        info = transaction_info(session)
    async with AsyncSession(homes.databases.engine(Home.RU)) as bare:
        with pytest.raises(NotAHomeTransactionError):
            await outbox.add(bare, NoteWritten(record_id=uuid.uuid4(), state=NoteState.DRAFT))

    assert (info.scope, info.read_only) == (scope, True)


@pytest.mark.parametrize(
    ("event_type", "payload"),
    [
        ("probe.note", "{}"),
        ("Probe.note.written", "{}"),
        ("probe.note.written", "[]"),
        ("probe.note.written", '"text"'),
    ],
)
@pytest.mark.usefixtures("homes")
async def test_the_database_refuses_a_malformed_type_or_payload(
    run_slot: RunSlot, event_type: str, payload: str
) -> None:
    connection = run_slot.claimed.connections[Home.RU]

    with pytest.raises(psycopg.errors.CheckViolation):
        await connection.execute(
            "INSERT INTO outbox_messages (id, event_type, version, payload) "
            "VALUES (%s, %s, 1, %s::jsonb)",
            (uuid.uuid7(), event_type, payload),
        )
