"""The catalog lists every event and subscription once and routes each event type."""

from datetime import timedelta
from typing import ClassVar
from uuid import UUID

import pytest
from redis.asyncio import Redis

from shosai.core.events.catalog import EventCatalog, EventTypes
from shosai.core.events.domain_event import DomainEvent
from shosai.core.events.subscriptions import EventSubscription, ReceivedEvent
from shosai.core.events.system import PURGE_OUTBOX, RELAY_OUTBOX
from shosai.core.tasks.declaration import RETRY_TRANSIENT
from shosai.core.tasks.queues import TaskQueue
from tests.core.events.bench import (
    Applied,
    NoteArchived,
    NoteState,
    NoteWritten,
    event_bench,
    recording,
)
from tests.harness.database_access import DatabaseAccess

APPLIED = Applied()


class OtherNoteWritten(DomainEvent):
    """A second class claiming the type of `NoteWritten`."""

    event_type: ClassVar[str] = "probe.note.written"
    version: ClassVar[int] = 2

    record_id: UUID


async def ignore(_session: object, _received: ReceivedEvent[NoteArchived]) -> None:
    """A handler that applies nothing."""


def test_each_event_type_routes_to_the_delivery_task_of_each_subscriber() -> None:
    mail = recording("mail.welcome", APPLIED, queue=TaskQueue.CRITICAL)
    index = recording("search.index_note", APPLIED)
    catalog = EventCatalog([NoteWritten, NoteArchived], [mail, index])

    routes = catalog.routes_of(NoteWritten.event_type)

    assert routes is not None
    assert [(route.subscription, route.task.name) for route in routes] == [
        (mail, "events.mail.welcome"),
        (index, "events.search.index_note"),
    ]
    [route, _] = routes
    assert route.task.queue is TaskQueue.CRITICAL
    assert route.task.deadline == mail.deadline
    assert route.task.retry is RETRY_TRANSIENT
    assert catalog.routes_of(NoteArchived.event_type) == ()
    assert catalog.routes_of("probe.note.unknown") is None
    assert catalog.all_routes() == routes


def test_only_the_listed_class_of_a_type_may_be_written() -> None:
    catalog = EventCatalog([NoteWritten], [])

    assert catalog.lists(NoteWritten(record_id=UUID(int=1), state=NoteState.DRAFT))
    assert not catalog.lists(OtherNoteWritten(record_id=UUID(int=1)))
    assert not catalog.lists(NoteArchived(record_id=UUID(int=1)))


def test_a_type_is_listed_by_one_class_and_a_consumer_subscribes_once() -> None:
    with pytest.raises(ValueError, match="двумя классами"):
        EventCatalog([NoteWritten, OtherNoteWritten], [])
    with pytest.raises(ValueError, match="подписан дважды"):
        EventCatalog([NoteWritten], [recording("mail.welcome", APPLIED)] * 2)


def test_a_subscription_to_an_unlisted_event_is_refused() -> None:
    archived = EventSubscription(
        consumer="mail.archived",
        event=NoteArchived,
        queue=TaskQueue.DEFAULT,
        deadline=timedelta(seconds=5),
        handle=ignore,
    )

    with pytest.raises(ValueError, match="вне каталога"):
        EventCatalog([NoteWritten], [archived])


@pytest.mark.parametrize(
    "consumer", ["welcome", "Mail.welcome", "mail.welcome-email", "mail." + "x" * 53]
)
def test_a_consumer_name_is_a_stable_slice_name(consumer: str) -> None:
    with pytest.raises(ValueError, match="имя потребителя"):
        recording(consumer, APPLIED)


def test_every_role_registers_the_relay_the_purge_and_each_delivery(
    valkey: Redis, database_access: DatabaseAccess
) -> None:
    mail = recording("mail.welcome", APPLIED, queue=TaskQueue.CRITICAL)
    bench = event_bench(valkey, database_access, [mail, recording("search.index_note", APPLIED)])

    critical = bench.tasks.broker(TaskQueue.CRITICAL)
    assert critical.declaration(RELAY_OUTBOX.name) is RELAY_OUTBOX
    assert critical.declaration("events.mail.welcome") is not None
    assert bench.tasks.broker(TaskQueue.BULK).declaration(PURGE_OUTBOX.name) is PURGE_OUTBOX
    assert bench.tasks.broker().declaration("events.search.index_note") is not None


def test_the_event_types_alone_list_each_class_once() -> None:
    types = EventTypes([NoteWritten, NoteArchived])

    assert types.lists(NoteWritten(record_id=UUID(int=1), state=NoteState.DRAFT))
    assert not types.lists(OtherNoteWritten(record_id=UUID(int=1)))
    with pytest.raises(ValueError, match="двумя классами"):
        EventTypes([NoteWritten, OtherNoteWritten])
