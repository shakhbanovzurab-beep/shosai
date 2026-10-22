"""A recurring task's next one, made when it is marked done (KG-D5; tasks plan §3.8).

The next task copies its words, priority, who does it, its project and its checklist
unticked — not its comments — takes the schedule over and is due on the schedule's first
date after the original due day, not before the completer's today; a range keeps its
length. It goes to the top of the first to-do column of the board the completed task sits
on for the completer. One completed task makes at most one next one — the unique link to it
holds that under a repeat or a redelivery.
"""

from datetime import date, datetime
from typing import cast
from uuid import UUID

from sqlalchemy import Table, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.kernel.ids import new_id
from shosai.features.tasks.application.placements import CardSpot, first_column_of, place
from shosai.features.tasks.domain.recurrence import next_due, recurrence_of, shifted_start
from shosai.features.tasks.domain.tasks import TaskStatus
from shosai.features.tasks.infrastructure.board_records import TaskPlacementRecord
from shosai.features.tasks.infrastructure.task_records import TaskRecord
from shosai.features.tasks.infrastructure.thread_records import TaskSubtaskRecord

TASKS = cast("Table", TaskRecord.__table__)


async def next_of(
    session: AsyncSession, record: TaskRecord, viewer: UUID, today: date, now: datetime
) -> TaskRecord | None:
    """Make the next task of a recurring one just done; None when there is none to make."""
    if record.recurrence is None or record.due_on is None:
        return None
    rule = recurrence_of(record.recurrence)
    due_on = next_due(rule, record.due_on, today)
    task_id = new_id()
    made = await session.scalar(
        insert(TASKS)
        .values(
            id=task_id,
            user_id=record.user_id,
            org_id=record.org_id,
            access=record.access,
            title=record.title,
            description=record.description,
            status=TaskStatus.TODO.value,
            priority=record.priority,
            starts_on=shifted_start(record.starts_on, record.due_on, due_on),
            due_on=due_on,
            recurrence=record.recurrence,
            assignee_user_id=record.assignee_user_id,
            assignee_name=record.assignee_name,
            project_id=record.project_id,
            source=record.source,
            source_meeting_id=record.source_meeting_id,
            created_by=record.created_by,
            recurred_from_id=record.id,
            created_at=now,
            updated_at=now,
        )
        .on_conflict_do_nothing(
            index_elements=[TASKS.c.recurred_from_id],
            index_where=TASKS.c.recurred_from_id.is_not(None),
        )
        .returning(TASKS.c.id)
    )
    record.recurrence = None
    if made is None:
        return None
    await _copy_checklist(session, record, task_id, now)
    await _place_like(session, record.id, task_id, viewer, now)
    return await session.get(TaskRecord, task_id)


async def _copy_checklist(
    session: AsyncSession, done: TaskRecord, task_id: UUID, now: datetime
) -> None:
    """The done task's lines, in their order and unticked, on the next task."""
    lines = await session.execute(
        select(TaskSubtaskRecord.title, TaskSubtaskRecord.rank).where(
            TaskSubtaskRecord.task_id == done.id
        )
    )
    session.add_all(
        TaskSubtaskRecord(
            id=new_id(), task_id=task_id, user_id=done.user_id, org_id=done.org_id, title=title,
            done=False, rank=rank, created_at=now, updated_at=now,
        )
        for title, rank in lines
    )  # fmt: skip


async def _place_like(
    session: AsyncSession, done_id: UUID, task_id: UUID, viewer: UUID, now: datetime
) -> None:
    """Top of the first to-do column of the board the done task sits on for the completer."""
    board_id = await session.scalar(
        select(TaskPlacementRecord.board_id).where(
            TaskPlacementRecord.user_id == viewer, TaskPlacementRecord.task_id == done_id
        )
    )
    if board_id is None:
        return
    column_id = await first_column_of(session, board_id, TaskStatus.TODO)
    if column_id is not None:
        await place(session, viewer, task_id, CardSpot(board_id, column_id, 0), now)
