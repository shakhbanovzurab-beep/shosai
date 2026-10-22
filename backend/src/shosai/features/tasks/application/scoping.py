"""What every write of tasks shares: its space, its checks and what it touches besides the row.

Row-level security writes a workspace's rows only in a transaction scoped to it, so a write
first finds the space of the readable tasks it names, then opens its transaction there and
reads them again under lock. An assignee must be an active member of the task's workspace
and a project one of its projects. A person's change to a meeting's task touches the
meeting's set, so later revisions of its notes leave it be (TK-D3); a change the reader's
board shows raises that board's revision, as the cabinet's mocks do.
"""

from collections.abc import Collection
from datetime import datetime
from http import HTTPStatus
from typing import Final
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import Principal
from shosai.features.tasks.contracts import TaskNotFoundError
from shosai.features.tasks.domain.tasks import TaskRuleError
from shosai.features.tasks.infrastructure.board_records import BoardRecord, TaskPlacementRecord
from shosai.features.tasks.infrastructure.task_records import (
    TASK_RESOURCE,
    MeetingTaskSetRecord,
    TaskRecord,
)
from shosai.features.workspaces.contracts import (
    ACCESS_POLICY,
    MEMBERSHIP_READER,
    WORKSPACE_READER,
    Viewer,
)

INVALID: Final = "validation_error"


def rule_failure(error: TaskRuleError) -> AppError:
    """A broken rule of tasks as the API answers it."""
    return AppError(error.code, HTTPStatus.UNPROCESSABLE_CONTENT)


def invalid() -> AppError:
    """A request the contract refuses as a whole."""
    return AppError(INVALID, HTTPStatus.UNPROCESSABLE_CONTENT)


class Scoping:
    """Finds the space of tasks and checks what a write names."""

    def __init__(self, transactions: HomeTransactions, ports: PortDirectory) -> None:
        self._transactions = transactions
        self._ports = ports

    async def spaces_of(self, principal: Principal, task_ids: Collection[UUID]) -> set[UUID | None]:
        """The spaces of the named tasks, all of which the person must read; 404 otherwise."""
        readable = self._ports.get(ACCESS_POLICY).readable(TASK_RESOURCE, Viewer(principal.user_id))
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            rows = (
                await session.execute(
                    select(TaskRecord.id, TaskRecord.org_id).where(
                        TaskRecord.id.in_(list(task_ids)), readable
                    )
                )
            ).all()
        if len(rows) != len(set(task_ids)):
            raise TaskNotFoundError
        return {org_id for _, org_id in rows}

    async def space_of(self, principal: Principal, task_id: UUID) -> TenancyScope:
        """The scope a write of one task opens its transaction in."""
        (org_id,) = await self.spaces_of(principal, [task_id])
        return scope_in(principal, org_id)

    async def check_member(
        self, session: AsyncSession, org_id: UUID | None, user_id: UUID | None
    ) -> None:
        """An assignee is an active member of the task's workspace; 422 otherwise."""
        if user_id is None:
            return
        if org_id is None:
            raise invalid()
        members = await self._ports.get(MEMBERSHIP_READER).members(session, org_id, [user_id])
        if user_id not in members:
            raise invalid()

    async def check_project(
        self, session: AsyncSession, org_id: UUID | None, project_id: UUID | None
    ) -> None:
        """A project is one of the task's workspace's; 422 otherwise."""
        if project_id is None:
            return
        if org_id is None:
            raise invalid()
        found = await self._ports.get(WORKSPACE_READER).projects(session, org_id, [project_id])
        if project_id not in found:
            raise invalid()


def scope_in(principal: Principal, org_id: UUID | None) -> TenancyScope:
    """The person's scope, narrowed to a workspace when the write is one of its tasks."""
    return TenancyScope(home=principal.home, user_id=principal.user_id, org_id=org_id)


async def touch_sets(session: AsyncSession, meeting_ids: Collection[UUID], now: datetime) -> None:
    """A person changed tasks of these meetings: later revisions leave their sets be."""
    if not meeting_ids:
        return
    await session.execute(
        update(MeetingTaskSetRecord)
        .where(
            MeetingTaskSetRecord.meeting_id.in_(list(meeting_ids)),
            MeetingTaskSetRecord.touched_at.is_(None),
        )
        .values(touched_at=now, updated_at=now)
    )


async def raise_revisions(
    session: AsyncSession, viewer: UUID, task_ids: Collection[UUID], now: datetime
) -> None:
    """Raise the revision of each of the reader's boards where these tasks sit."""
    if not task_ids:
        return
    boards = select(TaskPlacementRecord.board_id).where(
        TaskPlacementRecord.user_id == viewer, TaskPlacementRecord.task_id.in_(list(task_ids))
    )
    await session.execute(
        update(BoardRecord)
        .where(BoardRecord.id.in_(boards))
        .values(revision=BoardRecord.revision + 1, updated_at=now)
    )
