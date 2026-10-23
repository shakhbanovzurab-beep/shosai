"""The small parts of a task's views: counts, checklist lines, the cover and attachments.

Each is read with its task or a whole list of them (`views`, `attachment_views`); the links
to previews come from files after the reader's transaction (ADR 0064).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Final
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Counts:
    """What a card counts of a task's checklist, comments and attachments."""

    subtasks_done: int = 0
    subtasks_total: int = 0
    comments: int = 0
    attachments: int = 0


NONE_COUNTED: Final = Counts()


@dataclass(frozen=True, slots=True)
class SubtaskView:
    """A line of a task's checklist."""

    id: UUID
    title: str
    done: bool


@dataclass(frozen=True, slots=True)
class PersonRef:
    """A person by id and name."""

    user_id: UUID
    name: str


@dataclass(frozen=True, slots=True)
class CoverRef:
    """A card's cover: the attachment, the object files holds for it and its preview's link."""

    attachment_id: UUID
    held_object_id: UUID
    preview_url: str | None = None


@dataclass(frozen=True, slots=True)
class AttachmentView:
    """A file of a task; its preview's link once files has made and signed it."""

    id: UUID
    held_object_id: UUID
    name: str
    content_type: str
    size_bytes: int
    image: bool
    added_by: PersonRef
    added_at: datetime
    preview_url: str | None = None
