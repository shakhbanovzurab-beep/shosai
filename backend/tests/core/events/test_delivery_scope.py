"""A consumer that names its effect's scope from the event is delivered in that scope (§12).

The event's own scope is its producer's; a lifecycle consumer — tasks following a member's
departure — writes the departed person's and their workspace's rows, so its delivery runs
as them, with the delivery mark in the same transaction.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
import sqlalchemy as sa
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.events.relay import OutboxRelay
from shosai.core.events.subscriptions import EventSubscription, ReceivedEvent
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.tasks.queues import TaskQueue
from tests.core.events.bench import NoteState, NoteWritten, event_bench, runs
from tests.core.events.test_delivery import write_note_with_effect
from tests.core.tasks.workbench import eventually, running
from tests.harness.database_access import DatabaseAccess

CONSUMER = "probe.as_named"
SETTINGS = sa.text("SELECT current_setting('app.user_id'), current_setting('app.org_id')")
PERSON = uuid.UUID("0190f0f0-0000-7000-8000-0000000000aa")
COMPANY = uuid.UUID("0190f0f0-0000-7000-8000-0000000000bb")


def as_named(event: NoteWritten, scope: TenancyScope) -> TenancyScope:
    """The scope of the probe's effect: a person and a company the event stands for."""
    del event
    return TenancyScope(scope.home, PERSON, COMPANY)


async def test_a_consumer_is_delivered_in_the_scope_it_names(
    valkey: Redis, homes: DatabaseAccess, probe_table: sa.TableClause
) -> None:
    seen: list[tuple[str, str]] = []

    async def handle(session: AsyncSession, received: ReceivedEvent[NoteWritten]) -> None:
        del received
        row = (await session.execute(SETTINGS)).one()
        seen.append((row[0], row[1]))

    subscription = EventSubscription(
        consumer=CONSUMER, event=NoteWritten, queue=TaskQueue.DEFAULT,
        deadline=timedelta(seconds=30), handle=handle, scope=as_named,
    )  # fmt: skip
    bench = event_bench(valkey, homes, [subscription])
    await write_note_with_effect(bench, homes, probe_table, Home.RU)

    async with running(bench.tasks.broker()):
        await OutboxRelay(bench.resources, bench.tasks.system.sender).relay(Home.RU)
        await eventually(runs(bench, TaskQueue.DEFAULT, subscription.task_name, "succeeded"))

    assert seen == [(str(PERSON), str(COMPANY))]


def elsewhere(event: NoteWritten, scope: TenancyScope) -> TenancyScope:
    """A scope in another home than the event's."""
    del event, scope
    return TenancyScope(Home.EU, PERSON, COMPANY)


async def nothing(session: AsyncSession, received: ReceivedEvent[NoteWritten]) -> None:
    """A handler that writes nothing."""
    del session, received


def test_a_named_scope_never_moves_the_effect_to_another_home() -> None:
    subscription = EventSubscription(
        consumer=CONSUMER, event=NoteWritten, queue=TaskQueue.DEFAULT,
        deadline=timedelta(seconds=30), handle=nothing, scope=elsewhere,
    )  # fmt: skip
    event = NoteWritten(record_id=uuid.uuid4(), state=NoteState.FINAL)
    received = ReceivedEvent(event, uuid.uuid4(), 1, datetime.now(UTC), TenancyScope(Home.RU))

    with pytest.raises(ValueError, match="дом"):
        subscription.effect_scope(received)
