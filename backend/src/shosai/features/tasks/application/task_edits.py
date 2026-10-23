"""Changing a task by field presence (tasks plan §3.3, §3.8, §3.11).

Whoever may read a task may change it (TK-D2). A field left out stays and `null` clears;
without a due day there is no start, a start is not after the due day, a schedule set on a
task without a due day gives it the first date from today. A member does only a workspace's
task and is an active member of it; a name as written goes only on a personal task. A field
the person sets loses Leo's mark on it. Marking a recurring task done makes its next one. A
status changed without a move works the stopwatch on the changer's board as the move its
next read makes (§3.9); plan and fact are minutes, and a Jira task has neither.
The change touches the meeting's set of the task, raises the revision of the reader's board
where it sits, and publishes its events — all in the change's transaction.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from http import HTTPStatus
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.errors import AppError
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import Principal
from shosai.features.tasks.application import clock_rules
from shosai.features.tasks.application.recurring import next_of
from shosai.features.tasks.application.scoping import (
    Scoping,
    invalid,
    locked_task,
    raise_revisions,
    rule_failure,
    touch_sets,
)
from shosai.features.tasks.application.task_events import NEW, before_of, events_of
from shosai.features.tasks.application.task_reads import TaskReads, zone_of
from shosai.features.tasks.application.views import TaskView
from shosai.features.tasks.domain.changes import (
    UNSET,
    Schedule,
    TaskChange,
    Unset,
    checked_change,
    leo_fields_after,
    schedule_after,
)
from shosai.features.tasks.domain.recurrence import recurrence_json, recurrence_of
from shosai.features.tasks.domain.tasks import (
    LeoField,
    TaskRuleError,
    TaskSource,
    TaskStatus,
    completed_at_after,
)
from shosai.features.tasks.infrastructure.attachment_records import TaskAttachmentRecord
from shosai.features.tasks.infrastructure.task_records import TaskRecord


@dataclass(frozen=True, slots=True)
class Edit:
    """A person's change of a task: its fields, and the cover attachment if it is sent."""

    change: TaskChange
    cover: UUID | Unset | None = UNSET
    # Что прислали об исполнителе: имя — только личной задаче, участника — задаче пространства.
    sent_assignee_id: bool = False
    sent_assignee_name: bool = False
    # Карточку переносят следом (`Cards.change`): секундомер ведёт сам перенос.
    moving: bool = False


class TaskEdits:
    """Changes one task for a person who may read it."""

    def __init__(
        self,
        transactions: HomeTransactions,
        ports: PortDirectory,
        outbox: EventOutbox,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._ports = ports
        self._outbox = outbox
        self._clock = clock
        self._scoping = Scoping(transactions, ports)
        self._reads = TaskReads(transactions, ports)

    async def change(self, principal: Principal, task_id: UUID, edit: Edit) -> TaskView:
        """The task after the person's change, read back as the panel shows it."""
        scope = await self._scoping.space_of(principal, task_id)
        async with self._transactions.begin(scope) as session:
            record = await locked_task(session, self._ports, principal.user_id, task_id)
            await self.apply(session, principal.user_id, record, edit)
            view = await self._reads.view(session, principal.user_id, task_id)
        return await self._reads.signed(principal, view)

    async def apply(
        self, session: AsyncSession, viewer: UUID, record: TaskRecord, edit: Edit
    ) -> None:
        """The change on the locked row, in the caller's transaction of the task's scope: its
        rules, its next recurring task, its events and what it touches."""
        _refuse_misfits(record, edit)
        now = self._clock()
        today = now.astimezone(await zone_of(session, self._ports, viewer)).date()
        change, days = _checked(record, edit.change, today)
        if not isinstance(change.assignee, Unset):
            await self._scoping.check_member(session, record.org_id, change.assignee.user_id)
        if not isinstance(change.project_id, Unset):
            await self._scoping.check_project(session, record.org_id, change.project_id)
        if not isinstance(edit.cover, Unset):
            await _set_cover(session, record, edit.cover)
        before = before_of(record)
        status = TaskStatus(record.status)
        _write(record, change, days)
        leo = tuple(LeoField(field) for field in record.leo_fields)
        record.leo_fields = [field.value for field in leo_fields_after(leo, change)]
        made = await self._status(session, viewer, record, change, (today, now))
        if record.status != status.value and not edit.moving:
            await clock_rules.status_changed(session, viewer, record, status, now)
        record.version += 1
        record.updated_at = now
        await session.flush()
        events = [*events_of(before, record, viewer)]
        if made is not None:
            events += events_of(NEW, made, viewer)
        for event in events:
            await self._outbox.add(session, event)
        if record.source_meeting_id is not None and change.present():
            await touch_sets(session, [record.source_meeting_id], now)
        await raise_revisions(session, viewer, [record.id], now)

    async def _status(
        self,
        session: AsyncSession,
        viewer: UUID,
        record: TaskRecord,
        change: TaskChange,
        moment: tuple[date, datetime],
    ) -> TaskRecord | None:
        """Set the status; a recurring task marked done makes its next one, returned here."""
        if isinstance(change.status, Unset):
            return None
        today, now = moment
        status = TaskStatus(record.status)
        record.completed_at = completed_at_after(status, record.completed_at, change.status, now)
        record.status = change.status.value
        if change.status is TaskStatus.DONE and status is not TaskStatus.DONE:
            await session.flush()
            return await next_of(session, record, viewer, today, now)
        return None


def _refuse_misfits(record: TaskRecord, edit: Edit) -> None:
    """A member only on a workspace's task, a name only on a personal one; no plan or fact on
    a Jira task (KG-D8)."""
    if (record.org_id is None and edit.sent_assignee_id) or (
        record.org_id is not None and edit.sent_assignee_name
    ):
        raise invalid()
    tracked = {"plan_minutes", "fact_minutes"} & edit.change.present()
    if tracked and record.source == TaskSource.JIRA.value:
        raise AppError("jira_unsupported", HTTPStatus.CONFLICT)


async def _set_cover(session: AsyncSession, record: TaskRecord, cover: UUID | None) -> None:
    """The cover is an image attachment of the task, or none (KG-D3; a Jira task has none)."""
    if record.source == TaskSource.JIRA.value:
        raise AppError("jira_unsupported", HTTPStatus.CONFLICT)
    if cover is not None:
        image = await session.scalar(
            select(TaskAttachmentRecord.image).where(
                TaskAttachmentRecord.id == cover, TaskAttachmentRecord.task_id == record.id
            )
        )
        if image is None:
            raise AppError("attachment_not_found", HTTPStatus.NOT_FOUND)
        if not image:
            raise AppError("cover_not_image", HTTPStatus.CONFLICT)
    record.cover_attachment_id = cover


def _checked(record: TaskRecord, change: TaskChange, today: date) -> tuple[TaskChange, Schedule]:
    """The change within the task rules, and the task's days after it."""
    try:
        checked = checked_change(change, record.org_id)
        current = Schedule(
            record.starts_on,
            record.due_on,
            recurrence_of(record.recurrence) if record.recurrence else None,
        )
        return checked, schedule_after(current, checked, today)
    except TaskRuleError as error:
        raise rule_failure(error) from error


def _write(record: TaskRecord, change: TaskChange, days: Schedule) -> None:
    """Copy the change's fields and the task's days onto the row."""
    if not isinstance(change.title, Unset):
        record.title = change.title
    if not isinstance(change.description, Unset):
        record.description = change.description
    if not isinstance(change.priority, Unset):
        record.priority = change.priority.value if change.priority else None
    if not isinstance(change.assignee, Unset):
        record.assignee_user_id, record.assignee_name = (
            change.assignee.user_id,
            change.assignee.name,
        )
    if not isinstance(change.project_id, Unset):
        record.project_id = change.project_id
    if not isinstance(change.plan_minutes, Unset):
        record.plan_minutes = change.plan_minutes
    if not isinstance(change.fact_minutes, Unset):
        record.fact_minutes = change.fact_minutes
    record.starts_on, record.due_on = days.starts_on, days.due_on
    record.recurrence = recurrence_json(days.recurrence) if days.recurrence else None
