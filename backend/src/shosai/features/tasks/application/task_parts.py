"""The small parts of a task's views: counts, checklist lines, the cover and attachments, and
the facts of a task a card is made of.

Each is read with its task or a whole list of them (`views`, `attachment_views`); the links
to previews come from files after the reader's transaction (ADR 0064).
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Final, Protocol
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


class CardFacts(Protocol):
    """The fields of a task row a card shows and its access needs: a mapped task, or the
    lighter row a board reads (`CardRecord`)."""

    @property
    def id(self) -> UUID: ...
    @property
    def user_id(self) -> UUID: ...
    @property
    def org_id(self) -> UUID | None: ...
    @property
    def title(self) -> str: ...
    @property
    def status(self) -> str: ...
    @property
    def priority(self) -> str | None: ...
    @property
    def starts_on(self) -> date | None: ...
    @property
    def due_on(self) -> date | None: ...
    @property
    def assignee_user_id(self) -> UUID | None: ...
    @property
    def assignee_name(self) -> str | None: ...
    @property
    def recurrence(self) -> dict[str, object] | None: ...
    @property
    def leo_fields(self) -> list[str]: ...
    @property
    def source(self) -> str: ...
    @property
    def cover_attachment_id(self) -> UUID | None: ...


@dataclass(frozen=True, slots=True)
class CardRecord:
    """A task's card fields as one statement's row, without the mapper's bookkeeping."""

    id: UUID
    user_id: UUID
    org_id: UUID | None
    title: str
    status: str
    priority: str | None
    starts_on: date | None
    due_on: date | None
    assignee_user_id: UUID | None
    assignee_name: str | None
    recurrence: dict[str, object] | None
    leo_fields: list[str]
    source: str
    cover_attachment_id: UUID | None
