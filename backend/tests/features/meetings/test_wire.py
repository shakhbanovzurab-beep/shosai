"""What everyone in a call reads from the SFU: marks and attributes (meetings plan §1.2)."""

import json
import uuid

import pytest

from shosai.features.meetings.domain.wire import (
    ATTRIBUTE_MAX,
    RoomMarks,
    device_attributes,
    marks_of,
    room_metadata,
)


def test_the_metadata_carries_the_room_and_its_marks_but_not_the_home() -> None:
    room_id = uuid.uuid4()
    metadata = room_metadata(room_id, RoomMarks(notes=True, recording=False))

    assert json.loads(metadata) == {
        "v": 1,
        "room_id": str(room_id),
        "marks": {"notes": True, "recording": False},
    }
    assert "home" not in metadata
    assert marks_of(metadata) == RoomMarks(notes=True, recording=False)


@pytest.mark.parametrize(
    "metadata",
    [
        "",
        "not json",
        "[]",
        '{"v":2,"marks":{"notes":true,"recording":false}}',
        '{"v":1}',
        '{"v":1,"marks":{"notes":"yes","recording":false}}',
    ],
)
def test_metadata_that_is_not_meetings_has_no_marks(metadata: str) -> None:
    assert marks_of(metadata) is None


def test_device_attributes_take_the_known_keys_with_values_only_bounded() -> None:
    device = {
        "os": "macos",
        "os_version": "15.1",
        "client": "web",
        "client_version": None,
        "browser": "x" * 100,
        "colour": "red",
    }

    assert device_attributes(device) == {
        "device.os": "macos",
        "device.os_version": "15.1",
        "device.client": "web",
        "device.browser": "x" * ATTRIBUTE_MAX,
    }
