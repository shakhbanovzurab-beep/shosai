"""The write tools of Leo's `tasks` toolset: create, update, complete, move (tasks step 8).

Each runs only after the user approves the card the server writes for it (Leo §8.1, §8.4).
`tasks.create` makes 1 to 20 tasks under one approval, every one checked when the action is
proposed, so a batch either goes through whole or not at all; the others change one task the
user may read. A Jira card is not changed until Jira's writes come (step 13). The results
carry ids and the user's own choices only, so they have no provenance label.
"""

from datetime import date, timedelta
from typing import Final
from uuid import UUID

from pydantic import BaseModel, Field

from shosai.core.agent_tools.spec import Reversibility, ToolEffect, ToolSpec
from shosai.features.tasks.channels.agent_tool_models import Strict
from shosai.features.tasks.domain.tasks import Priority, TaskStatus

TOOLSET: Final = "tasks"
# Клиентский домен запросов кабинета, который перечитывается после записи.
TASKS_DOMAIN: Final = ("tasks",)
BATCH_MAX: Final = 20


class TaskDraftArgs(Strict):
    """One task to make."""

    title: str = Field(min_length=1, max_length=200, description="The task's title.")
    description: str = Field(default="", max_length=10_000, description="Markdown details.")
    due_on: date | None = Field(default=None, description="The due day, if any.")
    starts_on: date | None = Field(
        default=None, description="The first day of a range; only with a due day, not after it."
    )
    priority: Priority | None = Field(default=None, description="high, medium or low.")
    assignee_id: UUID | None = Field(
        default=None, description="A member of the workspace who does it; workspace tasks only."
    )
    assignee_name: str | None = Field(
        default=None, min_length=1, max_length=80,
        description="Who does a personal task, as the user names them; personal tasks only.",
    )  # fmt: skip
    project_id: UUID | None = Field(
        default=None, description="A project of the workspace; workspace tasks only."
    )


class CreateTasks(Strict):
    """Arguments of making tasks: all in one space, optionally on one of the user's boards."""

    tasks: list[TaskDraftArgs] = Field(
        min_length=1, max_length=BATCH_MAX, description="The tasks to make, 1 to 20."
    )
    workspace_id: UUID | None = Field(
        default=None, description="The workspace they belong to; null for personal tasks."
    )
    board_id: UUID | None = Field(
        default=None, description="The user's board to put them on, on top of its first column."
    )


class TasksCreated(BaseModel):
    """The tasks made, in the order given."""

    task_ids: list[UUID] = Field(description="The new tasks' ids.")


class UpdateTask(Strict):
    """Arguments of changing a task: only the fields given change; null clears a field."""

    task_id: UUID = Field(description="The id of a task the user may read.")
    title: str | None = Field(
        default=None, min_length=1, max_length=200, description="A new title."
    )
    description: str | None = Field(default=None, max_length=10_000, description="New details.")
    due_on: date | None = Field(default=None, description="A due day; null clears it.")
    starts_on: date | None = Field(default=None, description="A range's first day; null clears it.")
    priority: Priority | None = Field(default=None, description="high, medium, low; null clears.")
    assignee_id: UUID | None = Field(
        default=None, description="A member who does a workspace task; null clears."
    )
    assignee_name: str | None = Field(
        default=None, min_length=1, max_length=80,
        description="Who does a personal task, as named; null clears.",
    )  # fmt: skip


class TaskChanged(BaseModel):
    """The task after the change."""

    task_id: UUID = Field(description="The task's id.")
    title: str = Field(description="Its title.")
    status: TaskStatus = Field(description="todo, in_progress or done.")
    due_on: date | None = Field(description="Its due day; null if none.")
    priority: Priority | None = Field(description="Its priority; null if none.")


class CompleteTask(Strict):
    """Arguments of marking a task done, or open again."""

    task_id: UUID = Field(description="The id of a task the user may read.")
    done: bool = Field(default=True, description="True marks it done; false opens it again.")


class MoveTask(Strict):
    """Arguments of moving the user's card of a task."""

    task_id: UUID = Field(description="The id of a task the user may read.")
    board_id: UUID = Field(description="One of the user's boards.")
    column_id: UUID = Field(description="A column of that board; its kind becomes the status.")
    position: int = Field(default=0, ge=0, le=10_000, description="Its place, 0 the top.")


class TaskMoved(BaseModel):
    """Where the card is now."""

    task_id: UUID = Field(description="The task's id.")
    board_id: UUID = Field(description="The board.")
    column_id: UUID = Field(description="The column.")
    status: TaskStatus = Field(description="The task's status now.")


def write_spec[I: BaseModel, O: BaseModel](
    name: str, description: str, models: tuple[type[I], type[O]], reversibility: Reversibility
) -> ToolSpec[I, O]:
    """A write of the toolset."""
    return ToolSpec(
        name=name, toolset=TOOLSET, description=description, input=models[0],
        output=models[1], effect=ToolEffect.WRITE, reversibility=reversibility,
        result_budget=600, timeout=timedelta(seconds=10), invalidates=TASKS_DOMAIN,
    )  # fmt: skip


CREATE: Final = write_spec(
    "tasks.create",
    "Make 1 to 20 tasks in one go, all personal or all in one workspace, optionally on one of"
    " the user's boards. Every task is checked before the user approves; if one is not valid,"
    " none is made. The user approves the batch first.",
    (CreateTasks, TasksCreated),
    Reversibility.COMPENSABLE,
)
UPDATE: Final = write_spec(
    "tasks.update",
    "Change a task's title, details, days, priority or who does it. Only the fields given"
    " change; null clears one. The user approves the change first.",
    (UpdateTask, TaskChanged),
    Reversibility.REVERSIBLE,
)
COMPLETE: Final = write_spec(
    "tasks.complete",
    "Mark a task done, or open it again. A recurring task's next one is made when it is done."
    " The user approves it first.",
    (CompleteTask, TaskChanged),
    Reversibility.REVERSIBLE,
)
MOVE: Final = write_spec(
    "tasks.move",
    "Move the user's card of a task to a column of one of their boards; the column's kind"
    " becomes the task's status. The user approves the move first.",
    (MoveTask, TaskMoved),
    Reversibility.REVERSIBLE,
)
WRITE_TOOLS: Final = (CREATE, UPDATE, COMPLETE, MOVE)
