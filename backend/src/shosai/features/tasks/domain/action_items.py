"""A meeting's action items as tasks, and when a new revision of its notes may change them (TK-D3).

Every action item of a kept meeting is a task of the meeting's owner, in the meeting's
space, keyed by its finding. A meeting's tasks form one set: a newer revision of the
notes replaces the set only while the person has touched none of its tasks; once one is
ticked, edited, moved, assigned or deleted, the set stays as it is and later revisions add
nothing — no duplicates, no lost ticks. Revisions only grow, so a late or repeated event of
an older revision changes nothing. Who does a task is the meeting's owner when the item
names the owner's own voice, otherwise the name the item gives: kept as written on a
personal task, matched to one member on a workspace's.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Final
from uuid import UUID

from shosai.features.tasks.domain.members import MemberName, match_member
from shosai.features.tasks.domain.tasks import ASSIGNEE_NAME_MAX, TITLE_MAX, Assignee

ELLIPSIS: Final = "…"
# Длинный пункт режется по последнему пробелу в хвосте заголовка, иначе — по символу.
WORD_CUT_WINDOW: Final = 40


@dataclass(frozen=True, slots=True)
class ActionItem:
    """An action item of a meeting's current notes, as notes' findings give it."""

    finding_id: UUID
    text: str
    owner_name: str | None
    owner_is_meeting_owner: bool
    due_on: date | None


@dataclass(frozen=True, slots=True)
class TaskSetState:
    """What tasks remember of a meeting's set: the revision applied and whether it is touched."""

    revision: int
    touched: bool


class Projection(StrEnum):
    """What a revision of a meeting's notes did to its set of tasks."""

    APPLIED = "applied"
    SKIPPED_TOUCHED = "skipped_touched"
    SKIPPED_SEEN = "skipped_seen"
    NOT_KEPT = "not_kept"


def projection_for(state: TaskSetState | None, revision: int, *, kept: bool) -> Projection:
    """Whether this revision replaces the meeting's set of tasks.

    A meeting not kept gets no tasks; a revision no newer than the one applied changes
    nothing; a touched set stays as it is.
    """
    if not kept:
        return Projection.NOT_KEPT
    if state is None:
        return Projection.APPLIED
    if revision <= state.revision:
        return Projection.SKIPPED_SEEN
    if state.touched:
        return Projection.SKIPPED_TOUCHED
    return Projection.APPLIED


@dataclass(frozen=True, slots=True)
class ProjectedTask:
    """The task an action item becomes."""

    finding_id: UUID
    title: str
    # Полный текст пункта, когда заголовок пришлось сократить.
    description: str
    due_on: date | None
    assignee: Assignee


@dataclass(frozen=True, slots=True)
class MeetingSpace:
    """Where the meeting's tasks live: its owner, and its workspace with the members, if any."""

    owner_id: UUID
    org_id: UUID | None = None
    members: tuple[MemberName, ...] = ()


def projected_tasks(items: Sequence[ActionItem], space: MeetingSpace) -> tuple[ProjectedTask, ...]:
    """One task per action item with text, in the notes' order."""
    tasks: list[ProjectedTask] = []
    for item in items:
        text = item.text.strip()
        if not text:
            continue
        title, description = _title_of(text)
        tasks.append(
            ProjectedTask(item.finding_id, title, description, item.due_on, _who(item, space))
        )
    return tuple(tasks)


def _title_of(text: str) -> tuple[str, str]:
    if len(text) <= TITLE_MAX:
        return text, ""
    head = text[: TITLE_MAX - len(ELLIPSIS)]
    space = head.rfind(" ", len(head) - WORD_CUT_WINDOW)
    cut = head[:space] if space > 0 else head
    return cut.rstrip() + ELLIPSIS, text


def _who(item: ActionItem, space: MeetingSpace) -> Assignee:
    if item.owner_is_meeting_owner:
        return Assignee() if space.org_id is None else Assignee(user_id=space.owner_id)
    name = (item.owner_name or "").strip()[:ASSIGNEE_NAME_MAX].strip()
    if not name:
        return Assignee()
    if space.org_id is not None:
        member = match_member(name, space.members)
        if member is not None:
            return Assignee(user_id=member)
    return Assignee(name=name)
