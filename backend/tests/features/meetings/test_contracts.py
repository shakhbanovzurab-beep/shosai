"""Meetings' public surface follows core's rules (meetings plan §3.2)."""

import inspect
import uuid
from datetime import UTC, datetime

import pytest

from shosai.composition.features import FEATURES
from shosai.core.events.domain_event import DomainEvent
from shosai.core.ports.keys import PortKey
from shosai.features.meetings import contracts
from shosai.features.meetings.contracts import LiveLine, MeetingNotFoundError, Side, events
from shosai.features.meetings.module import MEETINGS


def test_every_published_event_is_registered_and_named_for_the_slice() -> None:
    declared = {
        value
        for value in vars(events).values()
        if inspect.isclass(value) and issubclass(value, DomainEvent) and value is not DomainEvent
    }

    assert set(MEETINGS.events) == declared
    assert all(event.event_type.startswith("meetings.") for event in MEETINGS.events)
    assert MEETINGS in FEATURES


def test_the_ports_are_named_for_the_slice() -> None:
    keys = {value.name for value in vars(contracts).values() if isinstance(value, PortKey)}

    assert keys == {
        "meetings.live_meetings",
        "meetings.transcript_store",
        "meetings.live_signal",
        "meetings.meeting_reader",
        "meetings.meeting_findings",
    }


def test_a_missing_meeting_is_a_404_with_its_code() -> None:
    error = MeetingNotFoundError()

    assert (error.code, int(error.status)) == ("meeting_not_found", 404)


@pytest.mark.parametrize(("seq", "duration_ms"), [(0, 100), (1, -1)])
def test_a_live_line_needs_a_seq_from_one_and_a_length_from_zero(
    seq: int, duration_ms: int
) -> None:
    with pytest.raises(ValueError, match="строки"):
        LiveLine(uuid.uuid4(), seq, datetime(2026, 10, 19, tzinfo=UTC), duration_ms, Side.ME, "Да.")
