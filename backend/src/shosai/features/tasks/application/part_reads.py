"""The parts of tasks' views read for a whole list at once (tasks plan §3.12, §3.13).

The counts of checklists, comments and attachments are one aggregate per kind for every
task of a list, the covers' held objects one read, a panel's checklist in its order.
"""

from collections.abc import Collection, Mapping
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.features.tasks.application.task_parts import Counts, SubtaskView
from shosai.features.tasks.infrastructure.attachment_records import TaskAttachmentRecord
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
        .where(TaskSubtaskRecord.task_id.in_(ids))
        .group_by(TaskSubtaskRecord.task_id)
    )
    comments = await session.execute(
        select(TaskCommentRecord.task_id, func.count())
        .where(TaskCommentRecord.task_id.in_(ids))
        .group_by(TaskCommentRecord.task_id)
    )
    written = {task_id: count for task_id, count in comments}
    files = await session.execute(
        select(TaskAttachmentRecord.task_id, func.count())
        .where(TaskAttachmentRecord.task_id.in_(ids))
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
            TaskAttachmentRecord.id.in_(list(attachment_ids))
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
