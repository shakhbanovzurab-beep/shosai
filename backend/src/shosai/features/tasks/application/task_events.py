"""The events a change of a task publishes (TK-D10): ids, codes and the due day only.

A member made the one who does a workspace's task, a due day set, moved or cleared, a task
marked done or opened again — each once, compared with the task before the change. A new
task publishes what it starts with; a deleted one that it is gone.
"""

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from shosai.core.events.domain_event import DomainEvent
from shosai.features.tasks.contracts.events import (
    TaskAssigned,
    TaskCompleted,
    TaskDeleted,
    TaskDueChanged,
    TaskReopened,
)
from shosai.features.tasks.domain.tasks import TaskSource, TaskStatus
from shosai.features.tasks.infrastructure.task_records import TaskRecord


@dataclass(frozen=True, slots=True)
class Before:
    """What the events compare: who does the task, its due day and whether it is done."""

    assignee_user_id: UUID | None
    due_on: date | None
    done: bool


def before_of(record: TaskRecord) -> Before:
    """The task as it was before the change."""
    done = record.status == TaskStatus.DONE.value
    return Before(record.assignee_user_id, record.due_on, done)


NEW = Before(None, None, done=False)


def events_of(before: Before, record: TaskRecord, by: UUID | None) -> list[DomainEvent]:
    """The events of the change from `before` to the task as it is now."""
    found: list[DomainEvent] = []
    assigned = record.assignee_user_id
    if assigned is not None and record.org_id is not None and assigned != before.assignee_user_id:
        found.append(
            TaskAssigned(
                task_id=record.id,
                user_id=record.user_id,
                org_id=record.org_id,
                assignee_user_id=assigned,
                by_user_id=by,
            )
        )
    who = (record.id, record.user_id, record.org_id, record.assignee_user_id)
    if record.due_on != before.due_on:
        found.append(
            TaskDueChanged(
                task_id=who[0], user_id=who[1], org_id=who[2], assignee_user_id=who[3],
                due_on=record.due_on,
            )
        )  # fmt: skip
    done = record.status == TaskStatus.DONE.value
    if done and not before.done:
        found.append(
            TaskCompleted(
                task_id=who[0], user_id=who[1], org_id=who[2], assignee_user_id=who[3],
                source=TaskSource(record.source),
            )
        )  # fmt: skip
    elif before.done and not done:
        found.append(
            TaskReopened(task_id=who[0], user_id=who[1], org_id=who[2], assignee_user_id=who[3])
        )
    return found


def deleted_of(record: TaskRecord) -> TaskDeleted:
    """The event of a task gone for good."""
    return TaskDeleted(
        task_id=record.id,
        user_id=record.user_id,
        org_id=record.org_id,
        assignee_user_id=record.assignee_user_id,
    )
