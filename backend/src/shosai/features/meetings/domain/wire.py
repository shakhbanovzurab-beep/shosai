"""What everyone in a call reads from the SFU: the room's marks and the participants' attributes.

The marks — "Leo is taking notes" and "Recording" — live in the room's metadata, so every
participant sees them, not only the owner (the draft's lesson), and the join page shows them
before entering. A participant's attributes carry their device, set by the server at join
for the admin's screen, and their raised hand, set by the participant and lowered by them, by
the owner or by leaving. Attributes are strings: the hand is the time it was raised, absent
when lowered.
"""

import json
from dataclasses import dataclass
from typing import Final
from uuid import UUID

METADATA_VERSION: Final = 1
HAND: Final = "hand"
DEVICE_OS: Final = "device.os"
DEVICE_OS_VERSION: Final = "device.os_version"
DEVICE_CLIENT: Final = "device.client"
DEVICE_CLIENT_VERSION: Final = "device.client_version"
DEVICE_BROWSER: Final = "device.browser"
DEVICE_ATTRIBUTES: Final = (
    DEVICE_OS,
    DEVICE_OS_VERSION,
    DEVICE_CLIENT,
    DEVICE_CLIENT_VERSION,
    DEVICE_BROWSER,
)
# Значение атрибута — короткая строка; длиннее сервер не ставит.
ATTRIBUTE_MAX: Final = 64


@dataclass(frozen=True, slots=True)
class RoomMarks:
    """What runs on the server in a call, shown to everyone in it."""

    notes: bool
    recording: bool


def room_metadata(room_id: UUID, owner_id: UUID, marks: RoomMarks) -> str:
    """The SFU room's metadata: the room's id, its owner's principal and its marks, as JSON.

    The owner's principal lets every client name the host, which a participant's own
    attributes could not prove; it is already in the owner's identity whenever they are in
    the call. The owner's home is not in it: where the owner's data lives is not the
    participants' to know. The webhook finds the room by its LiveKit name.
    """
    body = {
        "v": METADATA_VERSION,
        "room_id": str(room_id),
        "owner": str(owner_id),
        "marks": {"notes": marks.notes, "recording": marks.recording},
    }
    return json.dumps(body, separators=(",", ":"))


def marks_of(metadata: str) -> RoomMarks | None:
    """The marks in a room's metadata; None when it is not meetings' metadata."""
    try:
        body = json.loads(metadata)
    except ValueError:
        return None
    if not isinstance(body, dict) or body.get("v") != METADATA_VERSION:
        return None
    marks = body.get("marks")
    if not isinstance(marks, dict):
        return None
    notes, recording = marks.get("notes"), marks.get("recording")
    if not isinstance(notes, bool) or not isinstance(recording, bool):
        return None
    return RoomMarks(notes=notes, recording=recording)


def device_attributes(device: dict[str, str | None]) -> dict[str, str]:
    """The device attributes set at join: the known keys, set values only, bounded."""
    return {
        key: value[:ATTRIBUTE_MAX]
        for key in DEVICE_ATTRIBUTES
        if (value := device.get(key.removeprefix("device."))) is not None and value
    }
