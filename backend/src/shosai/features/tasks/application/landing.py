"""What a board read sets right before it answers (tasks plan §3.5 flow 2, TK-D4; §3.14).

A card whose task's status left its column's kind — the task was ticked in a workspace, in
Today, by Leo — goes to the top of the first column of its status. The incoming board takes
the open tasks that came to its person and sit on none of their boards, on top of the first
column of their status, once: a task sits on at most one of a person's boards. Both happen
in the read's transaction under the board's lock and raise its revision, so the order the
person sees next stays.
"""

from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import ColumnElement, and_, exists, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.features.tasks.application.placements import CardSpot, put_on_top
from shosai.features.tasks.domain.boards import BOARD_OPEN_CARDS_MAX
from shosai.features.tasks.domain.placement import BoardColumn, first_column_of, spot_for
from shosai.features.tasks.domain.tasks import TaskSource, TaskStatus
from shosai.features.tasks.infrastructure.board_records import (
    BoardColumnRecord,
    BoardRecord,
    TaskPlacementRecord,
)
from shosai.features.tasks.infrastructure.task_records import TaskRecord

PLACED = TaskPlacementRecord


def waiting_for(viewer: UUID) -> ColumnElement[bool]:
    """Open tasks that came to the person (TK-D4) and sit on none of their boards."""
    return and_(
        TaskRecord.status != TaskStatus.DONE.value,
        or_(
            and_(TaskRecord.org_id.is_not(None), TaskRecord.assignee_user_id == viewer),
            and_(
                TaskRecord.org_id.is_(None),
                TaskRecord.user_id == viewer,
                TaskRecord.source == TaskSource.MEETING.value,
            ),
        ),
        ~exists().where(PLACED.user_id == viewer, PLACED.task_id == TaskRecord.id),
    )


async def board_columns(session: AsyncSession, board_id: UUID) -> list[BoardColumn]:
    """The board's columns, left to right."""
    rows = await session.execute(
        select(BoardColumnRecord.id, BoardColumnRecord.kind, BoardColumnRecord.position)
        .where(BoardColumnRecord.board_id == board_id)
        .order_by(BoardColumnRecord.position)
    )
    return [
        BoardColumn(column_id, TaskStatus(kind), position) for column_id, kind, position in rows
    ]


type Sitting = Sequence[tuple[UUID, UUID, TaskStatus]]


async def reconcile(
    session: AsyncSession,
    viewer: UUID,
    board: tuple[UUID, bool],
    rules: tuple[ColumnElement[bool], datetime],
    known: tuple[Sequence[BoardColumn], Sitting] | None = None,
) -> bool:
    """Align the board's cards with their statuses and land what waits on the incoming board;
    whether anything moved. The caller holds the board's lock; `rules` is the readable
    predicate and the moment; `known` the columns and the cards with their statuses when the
    caller has just read them."""
    board_id, incoming = board
    readable, now = rules
    columns, sitting = (
        known if known is not None else await _read(session, viewer, board_id, readable)
    )
    tops: defaultdict[UUID, list[UUID]] = defaultdict(list)
    for task_id, column_id, status in sitting:
        spot = spot_for(status, columns, column_id)
        if spot.to_top:
            tops[spot.column_id].append(task_id)
    if incoming:
        waiting = await session.execute(
            select(TaskRecord.id, TaskRecord.status)
            .where(readable, waiting_for(viewer))
            .order_by(TaskRecord.created_at.desc(), TaskRecord.id)
            .limit(BOARD_OPEN_CARDS_MAX)
        )
        for task_id, kind in waiting:
            target = first_column_of(columns, TaskStatus(kind))
            if target is not None:
                tops[target.column_id].append(task_id)
    for column_id, task_ids in tops.items():
        await put_on_top(session, viewer, CardSpot(board_id, column_id, 0), task_ids, now)
    if tops:
        await session.execute(
            update(BoardRecord)
            .where(BoardRecord.id == board_id)
            .values(revision=BoardRecord.revision + 1, updated_at=now)
        )
    return bool(tops)


async def _read(
    session: AsyncSession, viewer: UUID, board_id: UUID, readable: ColumnElement[bool]
) -> tuple[list[BoardColumn], list[tuple[UUID, UUID, TaskStatus]]]:
    columns = await board_columns(session, board_id)
    rows = await session.execute(
        select(PLACED.task_id, PLACED.column_id, TaskRecord.status)
        .join(TaskRecord, TaskRecord.id == PLACED.task_id)
        .where(PLACED.user_id == viewer, PLACED.board_id == board_id, readable)
    )
    return columns, [
        (task_id, column_id, TaskStatus(status)) for task_id, column_id, status in rows
    ]
