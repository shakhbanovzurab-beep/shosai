"""The shapes of a task's panel and a list's item (§3.8 to §3.10), beside the card's.

Subtasks, attachments and the values of fields off the reader's board come with their
steps (3b, 3c, 4); their shapes are here already, so the cabinet's generated types match
the mocks from the start.
"""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from shosai.features.tasks.channels.http.card_models import Card, StickerValue
from shosai.features.tasks.channels.http.out import Out
from shosai.features.tasks.domain.chat_source import Messenger
from shosai.features.tasks.domain.recurrence import Weekday
from shosai.features.tasks.domain.tasks import TaskSource


class DayRule(BaseModel):
    """Every day."""

    every: Literal["day"]


class WeekRule(BaseModel):
    """Every week on these days."""

    every: Literal["week"]
    weekdays: list[Weekday] = Field(min_length=1, max_length=7)


class MonthRule(BaseModel):
    """Every month on this day; 29 to 31 fall on a shorter month's last day."""

    every: Literal["month"]
    day: int = Field(ge=1, le=31)


type Recurrence = Annotated[DayRule | WeekRule | MonthRule, Field(discriminator="every")]


class SourceMeetingOut(Out):
    """The meeting a task came from."""

    id: UUID
    title: str
    started_at: datetime


class SourceFindingOut(Out):
    """The moment of the meeting that proves the action item."""

    quote: str
    start_ms: int


class ChatMessageOut(Out):
    """The chat message a task was made from: its link, when the messenger has one."""

    url: str | None
    sent_at: datetime


class ChatSourceOut(Out):
    """The team chat a task was made from (TK-D13)."""

    connection_id: UUID | None
    messenger: Messenger
    chat_title: str
    message: ChatMessageOut


class SourceOut(Out):
    """Where a task came from."""

    kind: TaskSource
    meeting: SourceMeetingOut | None
    finding: SourceFindingOut | None
    chat: ChatSourceOut | None = None


class PlacementOut(Out):
    """Where the reader's card of the task sits."""

    board_id: UUID
    column_id: UUID


class SubtaskOut(Out):
    """A line of the task's checklist."""

    id: UUID
    title: str
    done: bool


class PersonOut(Out):
    """A person by id and name."""

    user_id: UUID
    name: str


class AttachmentOut(Out):
    """A file of the task."""

    id: UUID
    name: str
    content_type: str
    size_bytes: int
    image: bool
    preview_url: str | None
    added_by: PersonOut
    added_at: datetime


class StickerColor(StrEnum):
    """The palette of fields' states and columns."""

    GRAY = "gray"
    RED = "red"
    ORANGE = "orange"
    AMBER = "amber"
    GREEN = "green"
    TEAL = "teal"
    BLUE = "blue"
    VIOLET = "violet"
    PINK = "pink"


class StickerStateOut(Out):
    """A state of a field."""

    id: UUID
    name: str
    color: StickerColor


class PersonOwner(Out):
    """A field of a person's boards."""

    user_id: UUID


class WorkspaceOwner(Out):
    """A field of a workspace's boards."""

    workspace_id: UUID


class CustomStickerOut(Out):
    """A field of the boards' owner: a set of states, a number or a text."""

    id: UUID
    kind: Literal["states", "number", "text"]
    name: str
    states: list[StickerStateOut]
    owner: PersonOwner | WorkspaceOwner


class OtherValueOut(Out):
    """A value of a field that is not on the reader's board, with the field."""

    sticker: CustomStickerOut
    value: StickerValue


class TaskDetail(Card):
    """A task as its panel shows it."""

    description: str
    recurrence: Recurrence | None
    other_values: list[OtherValueOut] = Field(default_factory=list)
    source: SourceOut
    subtasks: list[SubtaskOut] = Field(default_factory=list)
    attachments: list[AttachmentOut] = Field(default_factory=list)
    placement: PlacementOut | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    server_now: datetime


class TaskItem(Card):
    """A task in a list: its card, its project and meeting, and its moments."""

    project_id: UUID | None
    meeting_id: UUID | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class TodayOut(Out):
    """The person's Today."""

    items: list[TaskItem]
