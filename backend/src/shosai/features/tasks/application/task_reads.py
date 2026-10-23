"""Reading tasks: a page of them, Today, one task with its meeting, and the `TaskReader` port.

Every read is the policy's predicate in the query that reads (inv-14): a workspace's task
opens to its readers, a meeting's task also to the meeting's readers and its assignee, a
personal task to its owner. A list pages by its due day — no day last — or by its last
change, newest first. Today is the person's open personal tasks due on or before their day
and those they completed that day in their zone (TK-D11).
"""

from collections.abc import Collection, Mapping
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta
from enum import StrEnum
from typing import Final, cast
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel
from sqlalchemy import ColumnElement, Select, Table, and_, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.pagination.cursor import CursorCodec
from shosai.core.pagination.keyset import Keyset
from shosai.core.pagination.page import Page, PageRequest, page_of
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import ACCOUNT_PROFILE_READER, Principal
from shosai.features.tasks.application.attachment_views import attachments_of, with_previews
from shosai.features.tasks.application.part_reads import subtasks_of
from shosai.features.tasks.application.sources import with_source
from shosai.features.tasks.application.views import TaskView, context_of, task_of
from shosai.features.tasks.contracts import TaskFacts, TaskNotFoundError
from shosai.features.tasks.domain.tasks import Assignee, Priority, TaskSource, TaskStatus
from shosai.features.tasks.infrastructure.task_records import TASK_RESOURCE, TaskRecord
from shosai.features.workspaces.contracts import ACCESS_POLICY, Viewer

TODAY_MAX: Final = 200
TASKS: Final = cast("Table", TaskRecord.__table__)
# Без срока — после всех сроков: ключ сортировки не бывает NULL.
NO_DUE: Final = date(9999, 12, 31)
DUE_KEY: Final = func.coalesce(TASKS.c.due_on, literal(NO_DUE))
BY_DUE: Final = Keyset((DUE_KEY, TASKS.c.id))
BY_CHANGE: Final = Keyset((TASKS.c.updated_at, TASKS.c.id), descending=True)
OPEN: Final = (TaskStatus.TODO.value, TaskStatus.IN_PROGRESS.value)


class TaskSort(StrEnum):
    """The order of a list of tasks."""

    DUE = "due"
    RECENT = "recent"


class StatusFilter(StrEnum):
    """Which statuses a list shows."""

    OPEN = "open"
    DONE = "done"
    TODO = "todo"
    IN_PROGRESS = "in_progress"


class DuePosition(BaseModel):
    """Where a page by due day ended."""

    due: date
    task_id: UUID


class ChangePosition(BaseModel):
    """Where a page by last change ended."""

    updated_at: datetime
    task_id: UUID


BY_DUE_CURSOR: Final = CursorCodec("tasks.by_due", DuePosition)
BY_CHANGE_CURSOR: Final = CursorCodec("tasks.by_change", ChangePosition)


@dataclass(frozen=True, slots=True)
class TaskQuery:
    """What a list of tasks holds and in which order."""

    workspace_id: UUID | None = None
    personal: bool = False
    # "me", "none" или участник по id.
    assignee: str | UUID | None = None
    status: StatusFilter | None = None
    meeting_id: UUID | None = None
    project_id: UUID | None = None
    due_before: date | None = None
    text: str | None = None
    sort: TaskSort = TaskSort.DUE


class TaskReads:
    """Pages, Today, one task, and facts for other slices."""

    def __init__(self, transactions: HomeTransactions, ports: PortDirectory) -> None:
        self._transactions = transactions
        self._ports = ports

    def readable(self, viewer: Viewer) -> ColumnElement[bool]:
        """The tasks the viewer may read now."""
        return self._ports.get(ACCESS_POLICY).readable(TASK_RESOURCE, viewer)

    async def page(
        self, principal: Principal, query: TaskQuery, request: PageRequest
    ) -> Page[TaskView]:
        """A page of the tasks the person may read, filtered and ordered as asked."""
        viewer = Viewer(principal.user_id, query.workspace_id)
        statement = select(TaskRecord).where(self.readable(viewer), *_filters(query, viewer))
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            if query.sort is TaskSort.DUE:
                after_due = BY_DUE_CURSOR.decode(request.cursor) if request.cursor else None
                position = (after_due.due, after_due.task_id) if after_due else None
                rows = await _rows(session, BY_DUE.page(statement, position, request.limit))
            else:
                after = BY_CHANGE_CURSOR.decode(request.cursor) if request.cursor else None
                moved = (after.updated_at, after.task_id) if after else None
                rows = await _rows(session, BY_CHANGE.page(statement, moved, request.limit))
            context = await context_of(session, self._ports, principal.user_id, rows)
        views = await with_previews(
            self._ports,
            principal.scope(),
            [task_of(row, principal.user_id, context) for row in rows],
        )
        if query.sort is TaskSort.DUE:
            return page_of(
                views, request, BY_DUE_CURSOR, lambda view: view,
                lambda view: DuePosition(due=view.card.due_on or NO_DUE, task_id=view.card.id),
            )  # fmt: skip
        return page_of(
            views, request, BY_CHANGE_CURSOR, lambda view: view,
            lambda view: ChangePosition(updated_at=view.updated_at, task_id=view.card.id),
        )  # fmt: skip

    async def today(self, principal: Principal, day: date | None = None) -> list[TaskView]:
        """The person's Today: open personal tasks due by the day, and those done on it.

        The day is the cabinet's, in the person's zone; without one, today in that zone.
        """
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            zone = await zone_of(session, self._ports, principal.user_id)
            day = day or datetime.now(zone).date()
            start = datetime.combine(day, time(), zone)
            done_today = and_(
                TaskRecord.status == TaskStatus.DONE.value,
                TaskRecord.completed_at >= start,
                TaskRecord.completed_at < start + timedelta(days=1),
            )
            due = and_(TaskRecord.status.in_(OPEN), TaskRecord.due_on <= day)
            statement = (
                select(TaskRecord)
                .where(
                    TaskRecord.user_id == principal.user_id,
                    TaskRecord.org_id.is_(None),
                    or_(due, done_today),
                )
                .order_by(DUE_KEY, TaskRecord.created_at, TaskRecord.id)
                .limit(TODAY_MAX)
            )
            rows = await _rows(session, statement)
            context = await context_of(session, self._ports, principal.user_id, rows)
        views = [task_of(row, principal.user_id, context) for row in rows]
        return await with_previews(self._ports, principal.scope(), views)

    async def detail(self, principal: Principal, task_id: UUID) -> TaskView:
        """One task the person may read, with where their card sits; 404 otherwise."""
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            view = await self.view(session, principal.user_id, task_id)
        return await self.signed(principal, view)

    async def signed(self, principal: Principal, view: TaskView) -> TaskView:
        """The task with its previews' links, signed after the transaction that read it."""
        (signed,) = await with_previews(self._ports, principal.scope(), [view])
        return signed

    async def view(self, session: AsyncSession, viewer: UUID, task_id: UUID) -> TaskView:
        """One task the viewer may read, in the caller's transaction."""
        record = await session.scalar(
            select(TaskRecord).where(TaskRecord.id == task_id, self.readable(Viewer(viewer)))
        )
        if record is None:
            raise TaskNotFoundError
        context = await context_of(session, self._ports, viewer, [record], placed=True)
        view = replace(
            task_of(record, viewer, context),
            subtasks=await subtasks_of(session, task_id),
            attachments=await attachments_of(session, self._ports, task_id),
        )
        return await with_source(session, self._ports, Viewer(viewer), view)

    async def facts(
        self, session: AsyncSession, viewer: Viewer, task_ids: Collection[UUID]
    ) -> Mapping[UUID, TaskFacts]:
        """The `tasks.task_reader` port: the readable ones among `task_ids`."""
        if not task_ids:
            return {}
        rows = await _rows(
            session,
            select(TaskRecord).where(TaskRecord.id.in_(list(task_ids)), self.readable(viewer)),
        )
        return {row.id: _facts(row) for row in rows}


async def zone_of(session: AsyncSession, ports: PortDirectory, user_id: UUID) -> ZoneInfo:
    """The person's zone from their profile; UTC when none is known (ADR 0058)."""
    profile = await ports.get(ACCOUNT_PROFILE_READER).profile(session, user_id)
    if profile is None or not profile.timezone:
        return ZoneInfo("UTC")
    try:
        return ZoneInfo(profile.timezone)
    except ZoneInfoNotFoundError, ValueError:
        return ZoneInfo("UTC")


async def _rows(session: AsyncSession, statement: Select[TaskRecord]) -> list[TaskRecord]:
    return list((await session.scalars(statement)).all())


def _filters(query: TaskQuery, viewer: Viewer) -> list[ColumnElement[bool]]:
    found = [*_space(query), *_assignee(query.assignee, viewer), *_status(query.status)]
    if query.meeting_id is not None:
        found.append(TaskRecord.source_meeting_id == query.meeting_id)
    if query.project_id is not None:
        found.append(TaskRecord.project_id == query.project_id)
    if query.due_before is not None:
        found.append(TaskRecord.due_on <= query.due_before)
    if query.text:
        escaped = query.text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        found.append(TaskRecord.title.ilike(f"%{escaped}%", escape="\\"))
    return found


def _space(query: TaskQuery) -> list[ColumnElement[bool]]:
    found: list[ColumnElement[bool]] = []
    if query.workspace_id is not None:
        found.append(TaskRecord.org_id == query.workspace_id)
    if query.personal:
        found.append(TaskRecord.org_id.is_(None))
    return found


def _assignee(assignee: str | UUID | None, viewer: Viewer) -> list[ColumnElement[bool]]:
    if assignee == "me":
        return [TaskRecord.assignee_user_id == viewer.user_id]
    if assignee == "none":
        return [TaskRecord.assignee_user_id.is_(None), TaskRecord.assignee_name.is_(None)]
    if isinstance(assignee, UUID):
        return [TaskRecord.assignee_user_id == assignee]
    return []


def _status(status: StatusFilter | None) -> list[ColumnElement[bool]]:
    if status is None:
        return []
    statuses = {StatusFilter.OPEN: OPEN, StatusFilter.DONE: (TaskStatus.DONE.value,)}
    return [TaskRecord.status.in_(statuses.get(status, (status.value,)))]


def _facts(record: TaskRecord) -> TaskFacts:
    who = Assignee(record.assignee_user_id, record.assignee_name)
    return TaskFacts(
        task_id=record.id,
        user_id=record.user_id,
        org_id=record.org_id,
        title=record.title,
        status=TaskStatus(record.status),
        priority=Priority(record.priority) if record.priority else None,
        due_on=record.due_on,
        assignee=who,
        source=TaskSource(record.source),
        source_meeting_id=record.source_meeting_id,
    )
