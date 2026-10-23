"""The stopwatch's spans and a board's automations, in the transaction of the change (§3.9).

Each function runs in its caller's transaction, under the task's row lock or the board's, so
a person's stop and an automation land one after the other. A running span is opened only
where none runs — the partial unique index holds that under concurrent calls too — and
closed at the change's moment; the task's row keeps what the spans sum to with them. A
board's automations act only while it shows the stopwatch and never on a Jira task (KG-D8).
A status changed without a move — in the panel, Today, by Leo or a meeting — acts on the
changer's board as the move its next read makes; that read then leaves the clock alone, and
so does every other person's. A landed task starts through `tasks_start_landed`, as the
incoming board lands in the person's own scope, where row-level security writes no
workspace's rows.
"""

from collections.abc import Sequence
from datetime import datetime
from typing import Final
from uuid import UUID

from sqlalchemy import bindparam, delete, select, text, update
from sqlalchemy.dialects.postgresql import ARRAY, insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.types import DateTime, Uuid

from shosai.core.kernel.ids import new_id
from shosai.features.tasks.application.placements import board_columns
from shosai.features.tasks.domain.board_fields import StopwatchAutomations, SystemSticker
from shosai.features.tasks.domain.clocks import (
    Automations,
    at_ms,
    ms_between,
    runs_after_move,
    starts_on_arrival,
)
from shosai.features.tasks.domain.placement import spot_for
from shosai.features.tasks.domain.tasks import TaskSource, TaskStatus
from shosai.features.tasks.infrastructure.board_records import BoardRecord, TaskPlacementRecord
from shosai.features.tasks.infrastructure.clock_records import TaskClockSpanRecord
from shosai.features.tasks.infrastructure.task_records import TaskRecord

SPANS = TaskClockSpanRecord
START_LANDED: Final = text("SELECT tasks_start_landed(:task_ids, :column_ids, :at)").bindparams(
    bindparam("task_ids", type_=ARRAY(Uuid)),
    bindparam("column_ids", type_=ARRAY(Uuid)),
    bindparam("at", type_=DateTime(timezone=True)),
)


def automations_of(visibility: dict[str, bool], automations: dict[str, bool]) -> Automations:
    """A board's automations from its row; none while it hides the stopwatch."""
    if not visibility.get(SystemSticker.STOPWATCH.value, False):
        return None
    return StopwatchAutomations(**{key: bool(value) for key, value in automations.items()})


async def board_automations(session: AsyncSession, board_id: UUID) -> Automations:
    """The board's automations, read; none while it hides the stopwatch."""
    row = (
        await session.execute(
            select(BoardRecord.system_stickers, BoardRecord.stopwatch_automations).where(
                BoardRecord.id == board_id
            )
        )
    ).first()
    return None if row is None else automations_of(row[0], row[1])


async def start(
    session: AsyncSession, task: TaskRecord, column_id: UUID | None, now: datetime
) -> None:
    """Open a span in the column unless one runs; the task's row then runs since now."""
    moment = at_ms(now)
    opened = await session.scalar(
        insert(SPANS)
        .values(
            id=new_id(), task_id=task.id, user_id=task.user_id, org_id=task.org_id,
            column_id=column_id, started_at=moment,
        )
        .on_conflict_do_nothing(
            index_elements=[SPANS.task_id], index_where=SPANS.stopped_at.is_(None)
        )
        .returning(SPANS.id)
    )  # fmt: skip
    if opened is not None:
        task.stopwatch_since = moment
        task.stopwatch_total_ms = task.stopwatch_total_ms or 0
        task.stopwatch_by_column = task.stopwatch_by_column or {}


async def stop(session: AsyncSession, task: TaskRecord, now: datetime) -> bool:
    """Close the running span and add its time to the task's row; whether one ran."""
    moment = at_ms(now)
    closed = (
        await session.execute(
            update(SPANS)
            .where(SPANS.task_id == task.id, SPANS.stopped_at.is_(None))
            .values(stopped_at=moment)
            .returning(SPANS.column_id, SPANS.started_at)
        )
    ).first()
    if closed is None:
        return False
    column_id, started_at = closed
    took = ms_between(started_at, moment)
    by_column = dict(task.stopwatch_by_column or {})
    if column_id is not None:
        by_column[str(column_id)] = by_column.get(str(column_id), 0) + took
    task.stopwatch_since = None
    task.stopwatch_total_ms = (task.stopwatch_total_ms or 0) + took
    task.stopwatch_by_column = by_column
    return True


async def reset(session: AsyncSession, task: TaskRecord) -> None:
    """The stopwatch cleared, running or not."""
    await session.execute(delete(SPANS).where(SPANS.task_id == task.id))
    task.stopwatch_since = task.stopwatch_total_ms = task.stopwatch_by_column = None


def _clocked(task: TaskRecord) -> bool:
    return task.source != TaskSource.JIRA.value


async def arrived(
    session: AsyncSession, task: TaskRecord, spot: tuple[UUID, UUID], now: datetime
) -> None:
    """A task put on the board — made there or a recurring task's next one — starts its
    stopwatch if the board says so."""
    board_id, column_id = spot
    done = task.status == TaskStatus.DONE.value
    if _clocked(task) and starts_on_arrival(await board_automations(session, board_id), done=done):
        await start(session, task, column_id, now)


async def moved(
    session: AsyncSession, task: TaskRecord, move: tuple[UUID, UUID, UUID], now: datetime
) -> None:
    """A task moved on a board from a column to another: the old column's span closes, then
    the stopwatch goes on in the new one as the board says."""
    board_id, source, target = move
    if source == target or not _clocked(task):
        return
    automations = await board_automations(session, board_id)
    was_running = await stop(session, task, now)
    done = task.status == TaskStatus.DONE.value
    if runs_after_move(automations, was_running=was_running, done=done):
        await start(session, task, target, now)


async def shown_in(
    session: AsyncSession, viewer: UUID, task_id: UUID, status: TaskStatus
) -> tuple[UUID, UUID] | None:
    """The board and column where the reader's card of the task shows for this status — where
    its next read puts it, as a status changed elsewhere moves the card only then."""
    placed = await session.get(TaskPlacementRecord, (viewer, task_id))
    if placed is None:
        return None
    columns = await board_columns(session, placed.board_id)
    return placed.board_id, spot_for(status, columns, placed.column_id).column_id


async def status_changed(
    session: AsyncSession, viewer: UUID, task: TaskRecord, before: TaskStatus, now: datetime
) -> None:
    """A status changed without a move: on the changer's board, the move its next read makes,
    from where the card showed to the top of the first column of the new status."""
    if not _clocked(task):
        return
    placed = await session.get(TaskPlacementRecord, (viewer, task.id))
    if placed is None:
        return
    columns = await board_columns(session, placed.board_id)
    source = spot_for(before, columns, placed.column_id).column_id
    target = spot_for(TaskStatus(task.status), columns, source).column_id
    await moved(session, task, (placed.board_id, source, target), now)


async def start_landed(
    session: AsyncSession, landed: Sequence[tuple[UUID, UUID]], now: datetime
) -> None:
    """Start the tasks that just landed on the incoming board, each in its column; the
    caller checked that the board starts on arrival."""
    if not landed:
        return
    await session.execute(
        START_LANDED,
        {
            "task_ids": [task_id for task_id, _ in landed],
            "column_ids": [column_id for _, column_id in landed],
            "at": at_ms(now),
        },
    )
