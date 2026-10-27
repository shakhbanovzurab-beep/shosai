"""The events meetings publishes (meetings plan §3.2): ids, counts and seconds, nothing personal.

Consumers: proactive, later, notices a call that began or ended and a recording that is
ready. Each event names one room; a consumer reads what it needs through the slices' ports
before it acts.
"""

from typing import ClassVar
from uuid import UUID

from shosai.core.events.domain_event import DomainEvent


class CallStarted(DomainEvent):
    """A room's call began: its first participant reached the SFU."""

    event_type: ClassVar[str] = "meetings.call.started"
    version: ClassVar[int] = 1
    room_id: UUID
    call_id: UUID
    owner_id: UUID
    org_id: UUID | None = None


class CallEnded(DomainEvent):
    """A room's call ended: everyone left, and the SFU finished the room."""

    event_type: ClassVar[str] = "meetings.call.ended"
    version: ClassVar[int] = 1
    room_id: UUID
    call_id: UUID
    owner_id: UUID
    org_id: UUID | None = None
    seconds: int
    participants: int


class RecordingReady(DomainEvent):
    """A call's video recording became a File Manager file of the room's owner."""

    event_type: ClassVar[str] = "meetings.recording.ready"
    version: ClassVar[int] = 1
    recording_id: UUID
    room_id: UUID
    file_id: UUID
    owner_id: UUID
    org_id: UUID | None = None
    seconds: int
