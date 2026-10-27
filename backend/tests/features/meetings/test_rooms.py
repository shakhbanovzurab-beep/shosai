"""A room's title, close, change and ceiling (meetings plan §3.4, MR-D1, MR-D2)."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from shosai.features.meetings.domain.rooms import (
    TITLE_MAX,
    ClosedBy,
    Room,
    RoomRuleError,
    RoomState,
    changed,
    checked_title,
    closed,
    is_livekit_name,
    new_livekit_name,
    room_ceiling,
)

NOW = datetime(2026, 10, 27, 12, tzinfo=UTC)


def open_room() -> Room:
    return Room(
        id=uuid.uuid4(),
        owner_id=uuid.uuid4(),
        org_id=None,
        title=None,
        lk_room_name=new_livekit_name(),
        state=RoomState.OPEN,
        notes_on=True,
    )


def test_a_title_is_trimmed_optional_and_bounded() -> None:
    assert checked_title("  Планёрка  ") == "Планёрка"
    assert checked_title("週次ミーティング") == "週次ミーティング"
    assert checked_title(None) is None
    assert checked_title("   ") is None
    with pytest.raises(RoomRuleError) as error:
        checked_title("я" * (TITLE_MAX + 1))
    assert error.value.code == "title_too_long"


def test_a_closed_room_keeps_its_first_close() -> None:
    room = closed(open_room(), ClosedBy.OWNER, NOW)
    again = closed(room, ClosedBy.IDLE, NOW + timedelta(hours=1))

    assert room.state is RoomState.CLOSED
    assert not room.is_open
    assert (again.closed_by, again.closed_at) == (ClosedBy.OWNER, NOW)


def test_an_open_room_is_renamed_and_its_notes_switched_but_a_closed_one_is_not() -> None:
    room = open_room()

    renamed = changed(room, title="  Ретро ")
    assert (renamed.title, renamed.notes_on) == ("Ретро", True)
    assert changed(renamed, notes_on=False).notes_on is False
    assert changed(renamed, title="").title is None
    with pytest.raises(RoomRuleError) as error:
        changed(closed(room, ClosedBy.ADMIN, NOW), title="Ещё")
    assert error.value.code == "room_closed"


def test_livekit_names_are_new_or_carried_over_hex() -> None:
    name = new_livekit_name()

    assert is_livekit_name(name)
    assert len(name) == len("r-") + 16
    assert is_livekit_name("r-0a1b2c3d4e5f60718293a4b5c6d7e8f9")
    assert not is_livekit_name("room-1")
    assert not is_livekit_name("r-XYZ")
    assert new_livekit_name() != name


@pytest.mark.parametrize(
    ("plan_value", "platform", "ceiling"),
    [(None, 50, 50), (10, 50, 10), (100, 50, 50), (10, 4, 4), (1, 50, 2), (0, 50, 2), (None, 1, 2)],
)
def test_the_ceiling_is_the_plan_capped_by_the_platform_and_never_below_two(
    plan_value: int | None, platform: int, ceiling: int
) -> None:
    assert room_ceiling(plan_value, platform) == ceiling
