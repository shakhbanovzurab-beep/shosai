"""The parts of tasks' views read for a whole list at once (tasks plan §3.12, §3.13).

The counts of checklists, comments and attachments are one aggregate per kind for every
task of a list, the covers' held objects one read, a panel's checklist in its order. A read
that must stay within its round trips — a board — takes the counts and the cover in its own
statement instead, as per-row subqueries (`counted_columns`).
"""

from collections.abc import Collection, Mapping
from uuid import UUID

from sqlalchemy import ScalarSelect, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.features.tasks.application.task_parts import Counts, SubtaskView
from shosai.features.tasks.infrastructure.attachment_records import TaskAttachmentRecord
from shosai.features.tasks.infrastructure.id_lists import among
from shosai.features.tasks.infrastructure.task_records import TaskRecord
from shosai.features.tasks.infrastructure.thread_records import TaskCommentRecord, TaskSubtaskRecord


async def counts_of(session: AsyncSession, task_ids: Collection[UUID]) -> Mapping[UUID, Counts]:
    """The counts of the tasks' checklists and comments, one aggregate each."""
    if not task_ids:
        return {}
    ids = list(task_ids)
    lines = await session.execute(
        select(
            TaskSubtaskRecord.task_id,
            func.count().filter(TaskSubtaskRecord.done),
            func.count(),
        )
        .where(among(TaskSubtaskRecord.task_id, ids))
        .group_by(TaskSubtaskRecord.task_id)
    )
    comments = await session.execute(
        select(TaskCommentRecord.task_id, func.count())
        .where(among(TaskCommentRecord.task_id, ids))
        .group_by(TaskCommentRecord.task_id)
    )
    written = {task_id: count for task_id, count in comments}
    files = await session.execute(
        select(TaskAttachmentRecord.task_id, func.count())
        .where(among(TaskAttachmentRecord.task_id, ids))
        .group_by(TaskAttachmentRecord.task_id)
    )
    attached = {task_id: count for task_id, count in files}
    found = {task_id: (done, total) for task_id, done, total in lines}
    return {
        task_id: Counts(
            *found.get(task_id, (0, 0)), written.get(task_id, 0), attached.get(task_id, 0)
        )
        for task_id in ids
    }


async def covers_of(session: AsyncSession, attachment_ids: Collection[UUID]) -> Mapping[UUID, UUID]:
    """The held object of each cover attachment."""
    if not attachment_ids:
        return {}
    rows = await session.execute(
        select(TaskAttachmentRecord.id, TaskAttachmentRecord.held_object_id).where(
            among(TaskAttachmentRecord.id, attachment_ids)
        )
    )
    return {attachment_id: held_id for attachment_id, held_id in rows}


async def subtasks_of(session: AsyncSession, task_id: UUID) -> tuple[SubtaskView, ...]:
    """A task's checklist in its order."""
    rows = await session.execute(
        select(TaskSubtaskRecord.id, TaskSubtaskRecord.title, TaskSubtaskRecord.done)
        .where(TaskSubtaskRecord.task_id == task_id)
        .order_by(TaskSubtaskRecord.rank)
    )
    return tuple(SubtaskView(line_id, title, done) for line_id, title, done in rows)


type Counted = tuple[
    ScalarSelect[int], ScalarSelect[int], ScalarSelect[int], ScalarSelect[int], ScalarSelect[UUID]
]


def counted_columns() -> Counted:
    """A task row's lines done and in all, its comments and attachments, and its cover's held
    object, as subqueries of the row's own statement."""
    lines = TaskSubtaskRecord.task_id == TaskRecord.id
    return (
        select(func.count()).where(lines, TaskSubtaskRecord.done).scalar_subquery(),
        select(func.count()).where(lines).scalar_subquery(),
        select(func.count()).where(TaskCommentRecord.task_id == TaskRecord.id).scalar_subquery(),
        select(func.count()).where(TaskAttachmentRecord.task_id == TaskRecord.id).scalar_subquery(),
        select(TaskAttachmentRecord.held_object_id)
        .where(TaskAttachmentRecord.id == TaskRecord.cover_attachment_id)
        .scalar_subquery(),
    )


def counted_of(values: tuple[int, int, int, int, UUID | None]) -> tuple[Counts, UUID | None]:
    """The counts and the cover's held object a row's `counted_columns` carry."""
    done, total, comments, files, cover = values
    return Counts(done, total, comments, files), cover
