"""Tasks follow a workspace's lifecycle (tasks plan step 6; nfr-16).

A member's departure leaves no workspace task in their hands: the open ones assigned to them
are unassigned, the ones they own pass to the workspace's standing owner `member.removed`
names — with what hangs on them, whose rows carry the task's owner — and their places of
the workspace's tasks on their own boards go. The delivery runs as the departed person in
the workspace (`scope_of_departure`), so row-level security admits exactly the workspace's
rows and that person's own. A member who is active again by the time the event arrives is
left as they are, so a late delivery never undoes a new membership. A deleted project
leaves its tasks without it. Nothing here publishes events: no one was given a task.
"""

from collections.abc import Sequence
from datetime import datetime
from typing import Final
from uuid import UUID

import structlog
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.tasks.domain.tasks import TaskStatus
from shosai.features.tasks.infrastructure.attachment_records import (
    TaskAttachmentRecord,
    TaskAttachmentReleaseRecord,
)
from shosai.features.tasks.infrastructure.board_records import BoardRecord, TaskPlacementRecord
from shosai.features.tasks.infrastructure.clock_records import TaskClockSpanRecord
from shosai.features.tasks.infrastructure.sticker_records import TaskStickerValueRecord
from shosai.features.tasks.infrastructure.task_records import MeetingTaskSetRecord, TaskRecord
from shosai.features.tasks.infrastructure.thread_records import (
    TaskCommentRecord,
    TaskSubtaskRecord,
)
from shosai.features.workspaces.contracts import MEMBERSHIP_READER
from shosai.features.workspaces.contracts.events import MemberRemoved, ProjectDeleted

log = structlog.stdlib.get_logger(__name__)
# Строки при задачах пространства, где `user_id` — владелец задачи: уходят к преемнику с ней.
HANGING: Final = (
    TaskSubtaskRecord,
    TaskCommentRecord,
    TaskAttachmentRecord,
    TaskAttachmentReleaseRecord,
    TaskStickerValueRecord,
    TaskClockSpanRecord,
    MeetingTaskSetRecord,
)
PLACED = TaskPlacementRecord


def scope_of_departure(event: MemberRemoved, scope: TenancyScope) -> TenancyScope:
    """The departed person in the workspace they left, in the event's home."""
    return TenancyScope(scope.home, event.user_id, event.org_id)


def scope_of_workspace(event: ProjectDeleted, scope: TenancyScope) -> TenancyScope:
    """The event's person in the workspace whose project went."""
    return TenancyScope(scope.home, scope.user_id, event.org_id)


async def follow_departure(
    session: AsyncSession, ports: PortDirectory, removed: MemberRemoved, now: datetime
) -> None:
    """The departed member's tasks of the workspace unassigned or passed on; their places of
    them gone."""
    org_id, person = removed.org_id, removed.user_id
    members = await ports.get(MEMBERSHIP_READER).members(session, org_id, [person])
    if person in members:
        log.info("Участник снова в пространстве: уход не применён", org_id=str(org_id))
        return
    workspace_tasks = select(TaskRecord.id).where(TaskRecord.org_id == org_id)
    boards = list(
        await session.scalars(
            select(PLACED.board_id)
            .where(PLACED.user_id == person, PLACED.task_id.in_(workspace_tasks))
            .distinct()
        )
    )
    await session.execute(
        delete(PLACED).where(PLACED.user_id == person, PLACED.task_id.in_(workspace_tasks))
    )
    await _touch(session, boards, now)
    unassigned = await session.scalars(
        update(TaskRecord)
        .where(
            TaskRecord.org_id == org_id,
            TaskRecord.assignee_user_id == person,
            TaskRecord.status != TaskStatus.DONE.value,
        )
        .values(assignee_user_id=None, version=TaskRecord.version + 1, updated_at=now)
        .returning(TaskRecord.id)
    )
    passed = await _pass_on(session, removed, now)
    log.info(
        "Задачи ушедшего участника переданы",
        org_id=str(org_id), unassigned=len(list(unassigned)), passed=passed, boards=len(boards),
    )  # fmt: skip


async def _pass_on(session: AsyncSession, removed: MemberRemoved, now: datetime) -> int:
    """The tasks the member owned, and what hangs on them, become the successor's."""
    if removed.successor_user_id is None:
        log.warning(
            "У пространства нет владельца: задачи ушедшего участника остались за ним",
            org_id=str(removed.org_id),
        )
        return 0
    passed = await session.scalars(
        update(TaskRecord)
        .where(TaskRecord.org_id == removed.org_id, TaskRecord.user_id == removed.user_id)
        .values(user_id=removed.successor_user_id, version=TaskRecord.version + 1, updated_at=now)
        .returning(TaskRecord.id)
    )
    for model in HANGING:
        await session.execute(
            update(model)
            .where(model.org_id == removed.org_id, model.user_id == removed.user_id)
            .values(user_id=removed.successor_user_id)
        )
    return len(list(passed))


async def _touch(session: AsyncSession, boards: Sequence[UUID], now: datetime) -> None:
    if boards:
        await session.execute(
            update(BoardRecord)
            .where(BoardRecord.id.in_(boards))
            .values(revision=BoardRecord.revision + 1, updated_at=now)
        )


async def clear_project(session: AsyncSession, deleted: ProjectDeleted, now: datetime) -> None:
    """The deleted project's tasks stay in the workspace without it."""
    await session.execute(
        update(TaskRecord)
        .where(TaskRecord.org_id == deleted.org_id, TaskRecord.project_id == deleted.project_id)
        .values(project_id=None, version=TaskRecord.version + 1, updated_at=now)
    )
