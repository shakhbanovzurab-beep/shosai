"""A change of a task by field presence: a field left out stays, a field sent as null clears.

The draft read `None` as "unchanged", so a due day could never be cleared (draft lesson,
`me_tracker.py:666`). Here an absent field is `UNSET`, distinct from a null value.
"""

from dataclasses import dataclass, fields, replace
from datetime import date
from enum import Enum
from typing import Final
from uuid import UUID

from shosai.features.tasks.domain.tasks import (
    Assignee,
    Priority,
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
    due_on: date | Unset | None = UNSET
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
    return checked
