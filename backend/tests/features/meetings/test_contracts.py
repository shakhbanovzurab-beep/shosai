"""Meetings' public surface follows core's rules (meetings plan §3.2)."""

import inspect

from shosai.composition.features import FEATURES
from shosai.core.events.domain_event import DomainEvent
from shosai.core.ports.keys import Cardinality, PortKey
from shosai.features.meetings import contracts
from shosai.features.meetings.contracts import events
from shosai.features.meetings.module import MEETINGS


def test_every_published_event_is_registered_and_named_for_the_slice() -> None:
    declared = {
        value
        for value in vars(events).values()
        if inspect.isclass(value) and issubclass(value, DomainEvent) and value is not DomainEvent
    }

    assert set(MEETINGS.events) == declared
    assert {event.event_type for event in declared} == {
        "meetings.call.started",
        "meetings.call.ended",
        "meetings.recording.ready",
    }
    assert MEETINGS in FEATURES


def test_the_ports_are_named_for_the_slice() -> None:
    keys = {value.name: value for value in vars(contracts).values() if isinstance(value, PortKey)}

    assert set(keys) == {"meetings.room_links", "meetings.pending_events"}
    # Событий календаря может не быть вовсе: тогда никто не отвечает и ничего не ждёт.
    assert keys["meetings.pending_events"].cardinality is Cardinality.MANY
    assert keys["meetings.room_links"].cardinality is Cardinality.ONE


def test_a_room_not_found_is_a_404_with_its_code() -> None:
    error = contracts.RoomNotFoundError()

    assert error.code == "room_not_found"
    assert error.status == 404
