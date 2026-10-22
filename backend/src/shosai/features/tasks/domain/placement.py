"""Where a card sits on a board, and which tasks land on the incoming board (§3.5, TK-D4, TK-D5).

A card shows in a column of its task's status. When the status changed elsewhere — ticked
in Today, in a workspace, in Jira — the card goes to the top of the first column of its
status at the next read; moving a card to a column of another kind gives its task that
status. Tasks that come to a person — assigned to them in a workspace, or an action item
of their own meeting — land on the board they chose for incoming work when they are open
and on none of their boards. A board shows its open cards and those done in the last 30
days.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from shosai.features.tasks.domain.boards import DONE_VISIBLE, ColumnKind
from shosai.features.tasks.domain.tasks import TaskSource, TaskStatus


@dataclass(frozen=True, slots=True)
class BoardColumn:
    """A column of a board: its id, kind and place from the left."""

    column_id: UUID
    kind: ColumnKind
    position: int


def first_column_of(columns: Sequence[BoardColumn], kind: ColumnKind) -> BoardColumn | None:
    """The leftmost column of this kind, if the board has one."""
    of_kind = [column for column in columns if column.kind is kind]
    return min(of_kind, key=lambda column: column.position) if of_kind else None


@dataclass(frozen=True, slots=True)
class Spot:
    """Where a card shows: its column, and whether it goes to the top of it now."""

    column_id: UUID
    to_top: bool


def spot_for(status: TaskStatus, columns: Sequence[BoardColumn], current: UUID | None) -> Spot:
    """The column a card of this status shows in, given where it sits now.

    A card in a column of its status stays where it is; any other goes to the top of the
    first column of its status, which every board keeps.
    """
    by_id = {column.column_id: column for column in columns}
    sitting = by_id.get(current) if current is not None else None
    if sitting is not None and sitting.kind is status:
        return Spot(sitting.column_id, to_top=False)
    target = first_column_of(columns, status)
    if target is None:
        message = f"на доске нет колонки вида {status.value}"
        raise ValueError(message)
    return Spot(target.column_id, to_top=True)


def status_after_move(status: TaskStatus, target: ColumnKind) -> TaskStatus:
    """A card moved to a column takes its kind as the status; within one kind it keeps it."""
    return status if status is target else target


def shown_on_board(status: TaskStatus, completed_at: datetime | None, now: datetime) -> bool:
    """Whether a board shows the card: open, or done in the last 30 days."""
    if status is not TaskStatus.DONE:
        return True
    return completed_at is not None and now - completed_at <= DONE_VISIBLE


@dataclass(frozen=True, slots=True)
class IncomingFacts:
    """What decides whether a task comes to a person."""

    status: TaskStatus
    user_id: UUID
    org_id: UUID | None
    assignee_user_id: UUID | None
    source: TaskSource


def comes_to(person: UUID, task: IncomingFacts) -> bool:
    """Whether an open task came to the person: assigned to them in a workspace, or made
    from an action item of their own personal meeting.
    """
    if task.status is TaskStatus.DONE:
        return False
    if task.org_id is not None:
        return task.assignee_user_id == person
    return task.source is TaskSource.MEETING and task.user_id == person
