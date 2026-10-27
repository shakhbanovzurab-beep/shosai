"""Who a link admits, in which order it refuses, and what everyone may do (MR-D2)."""

import uuid
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from shosai.features.meetings.domain.joining import (
    IN_CALL,
    LIVEKIT_TOKEN_TTL,
    ROOM_PASS_TTL,
    CallRole,
    JoinFacts,
    JoinRefusal,
    call_role,
    join_refusal,
    may_remove,
)
from shosai.features.meetings.domain.principals import Principal
from shosai.features.meetings.domain.rooms import ClosedBy, Room, RoomState, closed

OWNER = uuid.uuid4()
ROOM = Room(
    id=uuid.uuid4(),
    owner_id=OWNER,
    org_id=None,
    title="Планёрка",
    lk_room_name="r-0011223344556677",
    state=RoomState.OPEN,
    notes_on=True,
)
GUEST = Principal.new_guest()
ADMITTED = JoinFacts(
    room=ROOM, owner_hidden=False, principal=GUEST, banned=False, present=3, ceiling=4
)


def test_an_open_room_with_space_admits_directly() -> None:
    assert join_refusal(ADMITTED) is None


@pytest.mark.parametrize(
    ("facts", "refusal"),
    [
        # Неизвестный токен и скрытый владелец неотличимы: ссылка ничего не раскрывает.
        (replace(ADMITTED, room=None), JoinRefusal.NOT_FOUND),
        (replace(ADMITTED, owner_hidden=True, banned=True, present=9), JoinRefusal.NOT_FOUND),
        (
            replace(ADMITTED, room=closed(ROOM, ClosedBy.IDLE, datetime.now(UTC)), banned=True),
            JoinRefusal.ROOM_FINISHED,
        ),
        (replace(ADMITTED, banned=True, present=4), JoinRefusal.REMOVED),
        (replace(ADMITTED, present=4), JoinRefusal.ROOM_FULL),
    ],
)
def test_refusals_are_decided_in_one_order(facts: JoinFacts, refusal: JoinRefusal) -> None:
    assert join_refusal(facts) is refusal


def test_the_owner_is_the_owner_on_every_device_and_cannot_be_removed() -> None:
    owner = Principal.of_user(OWNER)
    member = Principal.of_user(uuid.uuid4())

    assert call_role(ROOM, owner) is CallRole.OWNER
    assert call_role(ROOM, member) is CallRole.PARTICIPANT
    assert call_role(ROOM, GUEST) is CallRole.PARTICIPANT
    assert may_remove(ROOM, owner, GUEST)
    assert not may_remove(ROOM, owner, owner)
    assert not may_remove(ROOM, member, GUEST)


def test_everyone_in_a_call_has_the_same_rights_and_no_one_is_hidden() -> None:
    assert IN_CALL.can_publish
    assert IN_CALL.can_publish_data
    assert IN_CALL.can_update_own_metadata
    assert not IN_CALL.hidden


def test_a_livekit_token_is_short_lived_and_the_room_pass_lasts_a_working_day() -> None:
    assert LIVEKIT_TOKEN_TTL.total_seconds() == 600
    assert ROOM_PASS_TTL.total_seconds() == 12 * 3600
