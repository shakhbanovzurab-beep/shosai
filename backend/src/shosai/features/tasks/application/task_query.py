"""What a list of tasks holds and in which order, as the filters of its statement (§3.3)."""

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Final
from uuid import UUID

from sqlalchemy import ColumnElement

from shosai.features.tasks.domain.tasks import TaskStatus
from shosai.features.tasks.infrastructure.task_records import TaskRecord
from shosai.features.workspaces.contracts import Viewer

OPEN: Final = (TaskStatus.TODO.value, TaskStatus.IN_PROGRESS.value)


class TaskSort(StrEnum):
    """The order of a list of tasks."""

    DUE = "due"
    RECENT = "recent"


class StatusFilter(StrEnum):
    """Which statuses a list shows."""

    OPEN = "open"
    DONE = "done"
    TODO = "todo"
    IN_PROGRESS = "in_progress"


@dataclass(frozen=True, slots=True)
class TaskQuery:
    """What a list of tasks holds and in which order."""

    workspace_id: UUID | None = None
    personal: bool = False
    # "me", "none" или участник по id.
    assignee: str | UUID | None = None
    status: StatusFilter | None = None
    meeting_id: UUID | None = None
    project_id: UUID | None = None
    due_before: date | None = None
    text: str | None = None
    sort: TaskSort = TaskSort.DUE


def filters_of(query: TaskQuery, viewer: Viewer) -> list[ColumnElement[bool]]:
    found = [*_space(query), *_assignee(query.assignee, viewer), *_status(query.status)]
    if query.meeting_id is not None:
        found.append(TaskRecord.source_meeting_id == query.meeting_id)
    if query.project_id is not None:
        found.append(TaskRecord.project_id == query.project_id)
    if query.due_before is not None:
        found.append(TaskRecord.due_on <= query.due_before)
    if query.text:
        escaped = query.text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        found.append(TaskRecord.title.ilike(f"%{escaped}%", escape="\\"))
    return found


def _space(query: TaskQuery) -> list[ColumnElement[bool]]:
    found: list[ColumnElement[bool]] = []
    if query.workspace_id is not None:
        found.append(TaskRecord.org_id == query.workspace_id)
    if query.personal:
        found.append(TaskRecord.org_id.is_(None))
    return found


def _assignee(assignee: str | UUID | None, viewer: Viewer) -> list[ColumnElement[bool]]:
    if assignee == "me":
        return [TaskRecord.assignee_user_id == viewer.user_id]
    if assignee == "none":
        return [TaskRecord.assignee_user_id.is_(None), TaskRecord.assignee_name.is_(None)]
    if isinstance(assignee, UUID):
        return [TaskRecord.assignee_user_id == assignee]
    return []


def _status(status: StatusFilter | None) -> list[ColumnElement[bool]]:
    if status is None:
        return []
    statuses = {StatusFilter.OPEN: OPEN, StatusFilter.DONE: (TaskStatus.DONE.value,)}
    return [TaskRecord.status.in_(statuses.get(status, (status.value,)))]
