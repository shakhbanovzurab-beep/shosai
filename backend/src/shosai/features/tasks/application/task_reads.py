"""Reading tasks: a page of them, Today, one task with its meeting, and the `TaskReader` port.

Every read is the policy's predicate in the query that reads (inv-14): a workspace's task
opens to its readers, a meeting's task also to the meeting's readers and its assignee, a
personal task to its owner. A list pages by its due day — no day last — or by its last
change, newest first. Today is the person's open personal tasks due on or before their day
and those they completed that day in their zone (TK-D11).
"""

from collections.abc import Collection, Mapping
from dataclasses import replace
from datetime import date, datetime, time, timedelta
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
from shosai.features.tasks.application.part_reads import counted_columns, counted_of, subtasks_of
from shosai.features.tasks.application.sources import with_source
from shosai.features.tasks.application.task_parts import Counts
from shosai.features.tasks.application.task_query import (
    OPEN,
    TaskQuery,
    TaskSort,
    filters_of,
)
from shosai.features.tasks.application.value_reads import with_values
from shosai.features.tasks.application.views import TaskView, Wanted, context_of, task_of
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
        statement = select(TaskRecord).where(self.readable(viewer), *filters_of(query, viewer))
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            if query.sort is TaskSort.DUE:
                after_due = BY_DUE_CURSOR.decode(request.cursor) if request.cursor else None
                position = (after_due.due, after_due.task_id) if after_due else None
                rows, wanted = await _counted(
                    session, BY_DUE.page(statement, position, request.limit)
                )
            else:
                after = BY_CHANGE_CURSOR.decode(request.cursor) if request.cursor else None
                moved = (after.updated_at, after.task_id) if after else None
                rows, wanted = await _counted(
                    session, BY_CHANGE.page(statement, moved, request.limit)
                )
            context = await context_of(session, self._ports, principal.user_id, rows, wanted)
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
            rows, wanted = await _counted(session, statement)
            context = await context_of(session, self._ports, principal.user_id, rows, wanted)
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
        found, wanted = await _counted(
            session,
            select(TaskRecord).where(TaskRecord.id == task_id, self.readable(Viewer(viewer))),
        )
        if not found:
            raise TaskNotFoundError
        record = found[0]
        wanted = Wanted(placed=True, counted=wanted.counted)
        context = await context_of(session, self._ports, viewer, [record], wanted)
        view = replace(
            task_of(record, viewer, context),
            subtasks=await subtasks_of(session, task_id),
            attachments=await attachments_of(session, self._ports, task_id),
        )
        view = await with_values(session, view)
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


async def _counted(
    session: AsyncSession, statement: Select[TaskRecord]
) -> tuple[list[TaskRecord], Wanted]:
    """The tasks of the statement with their counts and covers in the same round trip."""
    rows = await session.execute(statement.add_columns(*counted_columns()))
    tasks: list[TaskRecord] = []
    counted: dict[UUID, tuple[Counts, UUID | None]] = {}
    for task, done, total, comments, files, cover in rows:
        tasks.append(task)
        counted[task.id] = counted_of((done, total, comments, files, cover))
    return tasks, Wanted(counted=counted)


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
