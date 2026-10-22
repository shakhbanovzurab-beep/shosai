"""The events tasks publishes (tasks plan §3.2, TK-D10): ids, codes and the due day only.

Consumers: proactive turns an assignment and a new due day into signals and withdraws a
candidate when its task is completed or deleted (Leo §9.3); hubs follows the tasks of its
boards. `user_id` is the task's owner and `assignee_user_id` the member who does it, so a
consumer finds whom a workspace task concerns without reading it; each consumer reads the
task's current state through `TaskReader` before it acts.
"""

from datetime import date
from typing import ClassVar
from uuid import UUID

from shosai.core.events.domain_event import DomainEvent
from shosai.features.tasks.domain.tasks import TaskSource


class TaskAssigned(DomainEvent):
    """A member of a workspace was made the one who does a task."""

    event_type: ClassVar[str] = "tasks.task.assigned"
    version: ClassVar[int] = 1
    task_id: UUID
    user_id: UUID
    org_id: UUID
    assignee_user_id: UUID
    # None — назначила встреча или синхронизация, а не человек.
    by_user_id: UUID | None = None


class TaskDueChanged(DomainEvent):
    """A task got a due day, another one, or none."""

    event_type: ClassVar[str] = "tasks.task.due_changed"
    version: ClassVar[int] = 1
    task_id: UUID
    user_id: UUID
    org_id: UUID | None = None
    assignee_user_id: UUID | None = None
    due_on: date | None = None


class TaskCompleted(DomainEvent):
    """A task was marked done."""

    event_type: ClassVar[str] = "tasks.task.completed"
    version: ClassVar[int] = 1
    task_id: UUID
    user_id: UUID
    org_id: UUID | None = None
    assignee_user_id: UUID | None = None
    source: TaskSource


class TaskReopened(DomainEvent):
    """A done task was opened again."""

    event_type: ClassVar[str] = "tasks.task.reopened"
    version: ClassVar[int] = 1
    task_id: UUID
    user_id: UUID
    org_id: UUID | None = None
    assignee_user_id: UUID | None = None


class TaskDeleted(DomainEvent):
    """A task is gone for good: deleted by a person, with its meeting, or with its board."""

    event_type: ClassVar[str] = "tasks.task.deleted"
    version: ClassVar[int] = 1
    task_id: UUID
    user_id: UUID
    org_id: UUID | None = None
    assignee_user_id: UUID | None = None
