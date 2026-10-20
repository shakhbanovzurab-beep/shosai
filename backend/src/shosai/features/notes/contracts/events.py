"""The events notes publishes (notes plan §3.2): ids, codes and counts, nothing personal.

Consumers: workspaces shares a meeting automatically when its notes are ready and
withdraws a deleted one. Commitments takes the findings of ready notes, and hubs files the
meeting. Proactive treats an ended meeting and ready notes as signals, and knowledge
indexes the transcript. Each consumer reads the meeting's current state through the
contracts before it acts.
"""

from typing import ClassVar
from uuid import UUID

from shosai.core.events.domain_event import DomainEvent
from shosai.features.notes.domain.meetings import EndCause, MeetingSource


class MeetingEnded(DomainEvent):
    """A meeting ended: by its client, by silence, at its ceiling, or as an import's recording."""

    event_type: ClassVar[str] = "notes.meeting.ended"
    version: ClassVar[int] = 1
    meeting_id: UUID
    user_id: UUID | None = None
    org_id: UUID | None = None
    source: MeetingSource
    cause: EndCause
    seconds: int


class NotesReady(DomainEvent):
    """A meeting's notes reached a new revision: its write-up and its findings."""

    event_type: ClassVar[str] = "notes.meeting.notes_ready"
    version: ClassVar[int] = 1
    meeting_id: UUID
    run_id: UUID
    user_id: UUID | None = None
    org_id: UUID | None = None
    revision: int
    key_points: int = 0
    decisions: int = 0
    action_items: int = 0
    promises: int = 0
    risks: int = 0
    questions: int = 0


class MeetingDeleted(DomainEvent):
    """A meeting was deleted: hidden from everyone now, gone for good after 7 days."""

    event_type: ClassVar[str] = "notes.meeting.deleted"
    version: ClassVar[int] = 1
    meeting_id: UUID
    user_id: UUID | None = None
    org_id: UUID | None = None


class MeetingRestored(DomainEvent):
    """Support brought a deleted meeting back within its 7 days; it is shared nowhere."""

    event_type: ClassVar[str] = "notes.meeting.restored"
    version: ClassVar[int] = 1
    meeting_id: UUID
    user_id: UUID | None = None
    org_id: UUID | None = None
