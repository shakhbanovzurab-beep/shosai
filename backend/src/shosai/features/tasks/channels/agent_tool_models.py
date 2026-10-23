"""The shapes of Leo's `tasks` toolset: arguments and results the model reads (tasks step 7).

Every description here is model-facing English (the model-facing test reads them). A task's
title, its assignee's name and a board's words may be a colleague's, a meeting's or a Jira
user's, so the tools label their results `task:foreign` (TK-D9, Leo §7.4). Times are the
person's: today is their day in their zone.
"""

from datetime import date
from typing import Final
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from shosai.features.tasks.application.leo_reads import DueWindow
from shosai.features.tasks.application.task_query import StatusFilter
from shosai.features.tasks.domain.tasks import Priority, TaskSource, TaskStatus

MAX_FOUND: Final = 20


class Strict(BaseModel):
    """Tool arguments: a field the schema lacks is refused."""

    model_config = ConfigDict(extra="forbid")


class SearchTasks(Strict):
    """Arguments of the task search; every filter given narrows the result."""

    query: str | None = Field(
        default=None, min_length=1, max_length=120,
        description="Words of the task's title, in any language.",
    )  # fmt: skip
    status: StatusFilter | None = Field(
        default=None,
        description="open is to do or in progress, or name one status, or null for any.",
    )
    due: DueWindow | None = Field(
        default=None,
        description=(
            "overdue: open tasks due before the user's today; today: due today; this_week: due"
            " from Monday to Sunday of the user's current week; null: any day or none."
        ),
    )
    workspace_id: UUID | None = Field(default=None, description="Only this workspace's tasks.")
    personal: bool = Field(default=False, description="Only the user's personal tasks.")
    meeting_id: UUID | None = Field(default=None, description="Only tasks from this meeting.")
    board_id: UUID | None = Field(default=None, description="Only tasks on this board of the user.")
    mine: bool = Field(
        default=False,
        description="Only what the user does: their personal tasks and those assigned to them.",
    )
    limit: int = Field(default=10, ge=1, le=MAX_FOUND, description="How many tasks to return.")


class WhoDoes(BaseModel):
    """Who does a task."""

    name: str = Field(description="The name, as the workspace shows it or as written.")
    is_you: bool = Field(description="Whether it is the user.")


class WorkspaceRef(BaseModel):
    """A workspace."""

    workspace_id: UUID = Field(description="The workspace's id.")
    name: str = Field(description="The workspace's name.")


class OnBoard(BaseModel):
    """Where the user's card of a task sits."""

    board_id: UUID = Field(description="The user's board.")
    board_name: str = Field(description="The board's name.")
    column_title: str = Field(description="The column's title.")


class TimeSpent(BaseModel):
    """The task's time, which Leo reads and never changes."""

    plan_minutes: int | None = Field(description="The planned minutes; null if none.")
    fact_minutes: int | None = Field(description="The minutes the user logged; null if none.")
    stopwatch_ms: int | None = Field(
        description="The stopwatch's time until now in milliseconds; null if it never ran."
    )
    stopwatch_running: bool = Field(description="Whether the stopwatch runs now.")


class FoundTask(BaseModel):
    """A task the user may read."""

    task_id: UUID = Field(description="The task's id, for the other tasks tools.")
    title: str = Field(description="The title, written by the user or someone else.")
    status: TaskStatus = Field(description="todo, in_progress or done.")
    priority: Priority | None = Field(description="high, medium, low or null.")
    starts_on: date | None = Field(description="The first day of a range; null if none.")
    due_on: date | None = Field(description="The due day; null if none.")
    overdue: bool = Field(description="Whether it is open and due before the user's today.")
    who: WhoDoes | None = Field(description="Who does it; null if no one is named.")
    workspace: WorkspaceRef | None = Field(description="Its workspace; null for a personal task.")
    source: TaskSource = Field(description="Where it came from.")
    meeting_id: UUID | None = Field(description="The meeting it came from; null if none.")
    recurring: bool = Field(description="Whether it repeats on a schedule.")
    on_board: OnBoard | None = Field(description="Where the user's card sits; null if on none.")
    time: TimeSpent = Field(description="Plan, fact and the stopwatch.")


class FoundTasks(BaseModel):
    """The matching tasks, by due day, undated last."""

    tasks: list[FoundTask] = Field(description="The matching tasks.")
    more: bool = Field(description="Whether more tasks match than were returned.")


class ListBoard(Strict):
    """Arguments of a board's read."""

    board_id: UUID | None = Field(
        default=None,
        description="The user's board; null: the board incoming work lands on, else the first.",
    )


class BoardCard(BaseModel):
    """A card on a board."""

    task_id: UUID = Field(description="The task's id.")
    title: str = Field(description="The title, written by the user or someone else.")
    priority: Priority | None = Field(description="high, medium, low or null.")
    due_on: date | None = Field(description="The due day; null if none.")
    who: str | None = Field(description="Who does it; null if no one is named.")


class BoardColumnCards(BaseModel):
    """A column with its cards, top first."""

    title: str = Field(description="The column's title.")
    kind: TaskStatus = Field(description="The status its cards have.")
    cards: list[BoardCard] = Field(description="Its first cards, top first.")
    more: int = Field(description="How many more cards the column holds.")


class BoardRef(BaseModel):
    """A board of the user."""

    board_id: UUID = Field(description="The board's id.")
    name: str = Field(description="The board's name.")


class BoardRead(BaseModel):
    """A board as the user sees it: open cards and those done in the last 30 days."""

    board: BoardRef = Field(description="The board read.")
    columns: list[BoardColumnCards] = Field(description="Its columns, left to right.")
    other_boards: list[BoardRef] = Field(description="The user's other boards.")
