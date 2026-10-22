"""A change of a task by field presence: a field left out stays, a field sent as null clears.

The draft read `None` as "unchanged", so a due day could never be cleared (draft lesson,
`me_tracker.py:666`). Here an absent field is `UNSET`, distinct from a null value.
"""

from dataclasses import dataclass, fields, replace
from datetime import date
from enum import Enum
from typing import Final
from uuid import UUID

from shosai.features.tasks.domain.recurrence import Recurrence, checked_recurrence, first_due
from shosai.features.tasks.domain.tasks import (
    Assignee,
    LeoField,
    Priority,
    TaskRule,
    TaskRuleError,
    TaskStatus,
    checked_assignee,
    checked_description,
    checked_title,
)


class Unset(Enum):
    """A field the change does not touch."""

    UNSET = "unset"


UNSET: Final = Unset.UNSET


@dataclass(frozen=True, slots=True)
class TaskChange:
    """The fields a person, Leo or a sync changes on a task; the others stay as they are."""

    title: str | Unset = UNSET
    description: str | Unset = UNSET
    status: TaskStatus | Unset = UNSET
    priority: Priority | Unset | None = UNSET
    starts_on: date | Unset | None = UNSET
    due_on: date | Unset | None = UNSET
    recurrence: Recurrence | Unset | None = UNSET
    assignee: Assignee | Unset = UNSET
    project_id: UUID | Unset | None = UNSET

    def present(self) -> frozenset[str]:
        """The names of the fields the change sets."""
        return frozenset(
            field.name for field in fields(self) if getattr(self, field.name) is not UNSET
        )


def checked_change(change: TaskChange, org_id: UUID | None) -> TaskChange:
    """The change with its texts trimmed and its rules checked for a task of this space."""
    checked = change
    if not isinstance(change.title, Unset):
        checked = replace(checked, title=checked_title(change.title))
    if not isinstance(change.description, Unset):
        checked = replace(checked, description=checked_description(change.description))
    if not isinstance(change.assignee, Unset):
        checked = replace(checked, assignee=checked_assignee(org_id, change.assignee))
    if isinstance(change.recurrence, Recurrence):
        checked = replace(checked, recurrence=checked_recurrence(change.recurrence))
    return checked


@dataclass(frozen=True, slots=True)
class Schedule:
    """A task's days and its recurrence."""

    starts_on: date | None
    due_on: date | None
    recurrence: Recurrence | None


def schedule_after(current: Schedule, change: TaskChange, today: date) -> Schedule:
    """The days after a change: without a due day no start, a start not after the due day,
    and a schedule set on a task without a due day gives it the first date from today.
    """
    due_on = current.due_on if isinstance(change.due_on, Unset) else change.due_on
    starts_on = current.starts_on if isinstance(change.starts_on, Unset) else change.starts_on
    recurrence = current.recurrence if isinstance(change.recurrence, Unset) else change.recurrence
    if due_on is None:
        starts_on = None
    if starts_on is not None and due_on is not None and starts_on > due_on:
        raise TaskRuleError(TaskRule.RANGE_INVALID)
    if recurrence is not None and due_on is None:
        due_on = first_due(recurrence, today)
    return Schedule(starts_on, due_on, recurrence)


def leo_fields_after(fields: tuple[LeoField, ...], change: TaskChange) -> tuple[LeoField, ...]:
    """Leo's marks left after a person's change: a field the person set loses its mark."""
    present = change.present()
    changed = {
        LeoField.ASSIGNEE: "assignee" in present,
        LeoField.DUE: bool(present & {"due_on", "starts_on"}),
        LeoField.PRIORITY: "priority" in present,
    }
    return tuple(field for field in fields if not changed[field])
