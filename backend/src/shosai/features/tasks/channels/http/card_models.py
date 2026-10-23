"""The shapes of a task the cabinet reads: the card, the task's panel and a list's item.

They follow `frontend/src/features/kanban/domain/*-contract.ts` and §3.8 to §3.10 of the plan
field for field. Fields whose steps have not come yet are already here, empty or null —
field values (step 4), clocks (step 4a), the chat source (step 4b), subtasks and comments
(step 3b), attachments and the cover (step 3c) — so the shapes match the mocks from the start.
The panel's shapes are in `detail_models`.
"""

from datetime import date, datetime
from uuid import UUID

from pydantic import Field

from shosai.features.tasks.channels.http.out import Out
from shosai.features.tasks.domain.chat_source import Messenger
from shosai.features.tasks.domain.tasks import LeoField, Priority, TaskStatus


class AssigneeOut(Out):
    """Who does the task: a member by id and name, or a name as written."""

    user_id: UUID | None
    name: str


class CoverOut(Out):
    """The card's cover: an image attachment of the task and its preview, once made."""

    attachment_id: UUID
    preview_url: str | None


class SpaceOut(Out):
    """The workspace a task belongs to, with its address in the cabinet."""

    workspace_id: UUID
    workspace_slug: str
    workspace_name: str


class JiraOut(Out):
    """The Jira issue a card mirrors."""

    key: str
    url: str
    type: str


class ChatLineOut(Out):
    """The team chat a task came from, as the card's face names it."""

    messenger: Messenger
    chat_title: str


class StateValue(Out):
    """A field value: one of its states."""

    state_id: str


class NumberValue(Out):
    """A field value: a number."""

    number: float


class TextValue(Out):
    """A field value: a text."""

    text: str


type StickerValue = StateValue | NumberValue | TextValue


class StopwatchOut(Out):
    """The stopwatch: closed time, per column, and since when it runs, if it runs."""

    running_since: datetime | None
    total_ms: int
    by_column: dict[str, int]


class TimerOut(Out):
    """The timer: running while `ends_at` is set, paused while `paused_left_ms` is."""

    length_ms: int
    ends_at: datetime | None
    paused_left_ms: int | None


class TimeTrackingOut(Out):
    """Plan and fact in minutes."""

    plan_minutes: int | None
    fact_minutes: int | None


class Card(Out):
    """A card: what a board shows of a task."""

    id: UUID
    title: str
    status: TaskStatus
    priority: Priority | None
    starts_on: date | None
    due_on: date | None
    assignee: AssigneeOut | None
    cover: CoverOut | None = None
    values: dict[str, StickerValue] = Field(default_factory=dict)
    subtasks_done: int = 0
    subtasks_total: int = 0
    comment_count: int = 0
    attachment_count: int = 0
    recurring: bool
    leo_fields: list[LeoField]
    space: SpaceOut | None
    jira: JiraOut | None = None
    source_chat: ChatLineOut | None = None
    can_delete: bool
    stopwatch: StopwatchOut | None = None
    timer: TimerOut | None = None
    time_tracking: TimeTrackingOut | None = None
