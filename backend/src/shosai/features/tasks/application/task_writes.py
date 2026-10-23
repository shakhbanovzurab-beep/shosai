"""Making and deleting tasks (tasks plan §3.3, TK-D1, TK-D2, TK-D6).

A task is made in the person's own space or in a workspace they are an active member of,
once per `Idempotency-Key` when one is sent. A hand-made workspace task opens to every
member (`organization`). A task is deleted at once, by its owner, or for a workspace's task
also by the workspace's owner and admins; a Jira task only goes with its board. The objects
of a deleted task's attachments go back to files after the commit. A batch is all or none,
and names tasks of one space at most besides the person's own: row-level security writes a
workspace's rows only in a transaction scoped to it.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime, timedelta
from http import HTTPStatus
from typing import Final
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.events.outbox import EventOutbox
from shosai.core.idempotency.ledger import (
    EffectKey,
    EffectLedger,
    EffectScope,
    account_key,
    fingerprint_of,
)
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.ids import new_id
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import Principal
from shosai.features.tasks.application.attachment_releases import AttachmentReleases
from shosai.features.tasks.application.scoping import (
    Scoping,
    lock_boards_of,
    raise_revisions,
    rule_failure,
    scope_in,
    touch_sets,
)
from shosai.features.tasks.application.task_events import NEW, deleted_of, events_of
from shosai.features.tasks.application.task_reads import TaskReads, zone_of
from shosai.features.tasks.application.views import TaskView, context_of, may_delete
from shosai.features.tasks.domain.changes import Schedule, TaskChange, schedule_after
from shosai.features.tasks.domain.chat_source import ChatOrigin, checked_origin
from shosai.features.tasks.domain.recurrence import Recurrence, recurrence_json
from shosai.features.tasks.domain.tasks import (
    Assignee,
    CreatedBy,
    Priority,
    TaskRule,
    TaskRuleError,
    TaskSource,
    TaskStatus,
    checked_assignee,
    checked_description,
    checked_title,
    completed_at_after,
)
from shosai.features.tasks.infrastructure.task_records import TASK_RESOURCE, TaskRecord
from shosai.features.workspaces.contracts import ACCESS_POLICY, MEMBERSHIP_READER, Viewer

TASK_CREATES: Final = EffectScope("tasks.task_create", timedelta(hours=24))


@dataclass(frozen=True, slots=True)
class NewTask:
    """A task a person makes by hand — or Leo from a team chat's message, which only the
    server's paths name (`chat`; TK-D13): a workspace's task, made by Leo."""

    title: str
    description: str = ""
    status: TaskStatus = TaskStatus.TODO
    priority: Priority | None = None
    starts_on: date | None = None
    due_on: date | None = None
    recurrence: Recurrence | None = None
    workspace_id: UUID | None = None
    assignee: Assignee = field(default_factory=Assignee)
    project_id: UUID | None = None
    chat: ChatOrigin | None = None
    # Кто пишет задачу: человек сам или Лео с его одобрения (шаг 8).
    created_by: CreatedBy = CreatedBy.PERSON


class TaskMade(BaseModel):
    """The outcome a repeated `Idempotency-Key` answers with."""

    task_id: UUID


class NewTaskPrint(BaseModel):
    """What a key's request is compared by: every field of the new task."""

    title: str
    description: str
    status: TaskStatus
    priority: Priority | None
    starts_on: date | None
    due_on: date | None
    recurrence: dict[str, object] | None
    workspace_id: UUID | None
    assignee_user_id: UUID | None
    assignee_name: str | None
    project_id: UUID | None


def print_of(draft: NewTask) -> NewTaskPrint:
    """The print of a new task's request."""
    return NewTaskPrint(
        title=draft.title,
        description=draft.description,
        status=draft.status,
        priority=draft.priority,
        starts_on=draft.starts_on,
        due_on=draft.due_on,
        recurrence=recurrence_json(draft.recurrence) if draft.recurrence else None,
        workspace_id=draft.workspace_id,
        assignee_user_id=draft.assignee.user_id,
        assignee_name=draft.assignee.name,
        project_id=draft.project_id,
    )


class TaskWrites:
    """Makes and deletes tasks."""

    def __init__(
        self,
        transactions: HomeTransactions,
        ports: PortDirectory,
        writers: tuple[EventOutbox, EffectLedger],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._ports = ports
        self._outbox, self._effects = writers
        self._clock = clock
        self._scoping = Scoping(transactions, ports)
        self._reads = TaskReads(transactions, ports)
        self._releases = AttachmentReleases(transactions, ports)

    async def create(
        self, principal: Principal, draft: NewTask, client_key: str | None
    ) -> TaskView:
        """A new task in the person's space or a workspace's; once per key when one is sent."""
        try:
            clean = checked_draft(draft)
        except TaskRuleError as error:
            raise rule_failure(error) from error
        async with self._transactions.begin(scope_in(principal, draft.workspace_id)) as session:
            await self.admit(session, principal, clean)
            if client_key is None:
                task_id = await self.make(session, principal, clean)
            else:
                effect = EffectKey(
                    TASK_CREATES,
                    account_key(principal.user_id, client_key),
                    fingerprint_of(print_of(clean)),
                )

                async def first() -> TaskMade:
                    return TaskMade(task_id=await self.make(session, principal, clean))

                task_id = (
                    await self._effects.once(session, effect, TaskMade, first)
                ).outcome.task_id
            view = await self._reads.view(session, principal.user_id, task_id)
        return await self._reads.signed(principal, view)

    async def admit(self, session: AsyncSession, principal: Principal, draft: NewTask) -> None:
        """The space is the person's to write in, and its member and project are its own."""
        if draft.workspace_id is not None:
            memberships = await self._ports.get(MEMBERSHIP_READER).active(
                session, principal.user_id
            )
            if draft.workspace_id not in {membership.org_id for membership in memberships}:
                raise AppError("workspace_not_found", HTTPStatus.NOT_FOUND)
        await self._scoping.check_member(session, draft.workspace_id, draft.assignee.user_id)
        await self._scoping.check_project(session, draft.workspace_id, draft.project_id)

    async def make(self, session: AsyncSession, principal: Principal, draft: NewTask) -> UUID:
        """A new task of an admitted, checked draft, with its events, in the caller's
        transaction of the draft's space."""
        now = self._clock()
        zone = await zone_of(session, self._ports, principal.user_id)
        try:
            days = schedule_after(
                Schedule(draft.starts_on, draft.due_on, draft.recurrence),
                TaskChange(),
                now.astimezone(zone).date(),
            )
            chat = _chat_of(draft)
        except TaskRuleError as error:
            raise rule_failure(error) from error
        record = TaskRecord(
            id=new_id(),
            user_id=principal.user_id,
            org_id=draft.workspace_id,
            access="organization" if draft.workspace_id else None,
            title=draft.title,
            description=draft.description,
            status=draft.status.value,
            priority=draft.priority.value if draft.priority else None,
            starts_on=days.starts_on,
            due_on=days.due_on,
            recurrence=recurrence_json(days.recurrence) if days.recurrence else None,
            completed_at=completed_at_after(TaskStatus.TODO, None, draft.status, now),
            assignee_user_id=draft.assignee.user_id,
            assignee_name=draft.assignee.name,
            project_id=draft.project_id,
            source=(TaskSource.MANUAL if chat is None else TaskSource.CHAT).value,
            created_by=(draft.created_by if chat is None else CreatedBy.LEO).value,
            leo_fields=[],
            created_at=now,
            updated_at=now,
            **_chat_columns(chat),
        )
        session.add(record)
        await session.flush()
        for event in events_of(NEW, record, principal.user_id):
            await self._outbox.add(session, event)
        return record.id

    async def delete(self, principal: Principal, task_ids: Sequence[UUID]) -> None:
        """Delete the tasks, all or none; each one the person may delete."""
        spaces = await self._scoping.spaces_of(principal, task_ids)
        workspaces = spaces - {None}
        if len(workspaces) > 1:
            raise AppError("validation_error", HTTPStatus.UNPROCESSABLE_CONTENT)
        org_id = next(iter(workspaces), None)
        readable = self._ports.get(ACCESS_POLICY).readable(TASK_RESOURCE, Viewer(principal.user_id))
        now = self._clock()
        async with self._transactions.begin(scope_in(principal, org_id)) as session:
            await lock_boards_of(session, principal.user_id, task_ids)
            rows = (
                await session.scalars(
                    select(TaskRecord)
                    .where(TaskRecord.id.in_(list(task_ids)), readable)
                    .order_by(TaskRecord.id)
                    .with_for_update()
                )
            ).all()
            if len(rows) != len(set(task_ids)):
                raise AppError("task_not_found", HTTPStatus.NOT_FOUND)
            context = await context_of(session, self._ports, principal.user_id, rows)
            if not all(may_delete(row, principal.user_id, context.roles) for row in rows):
                raise AppError("task_not_deletable", HTTPStatus.FORBIDDEN)
            await raise_revisions(session, principal.user_id, [row.id for row in rows], now)
            meetings = {row.source_meeting_id for row in rows if row.source_meeting_id}
            await touch_sets(session, meetings, now)
            for row in rows:
                await self._outbox.add(session, deleted_of(row))
                await session.delete(row)
        # Объекты вложений удалённых задач возвращаются files после коммита (ADR 0064).
        await self._releases.owner(scope_in(principal, None))
        if org_id is not None:
            await self._releases.owner(scope_in(principal, org_id))


def checked_draft(draft: NewTask) -> NewTask:
    """The draft with its words trimmed and its assignee fit for its space; a broken rule
    raises."""
    return replace(
        draft,
        title=checked_title(draft.title),
        description=checked_description(draft.description),
        assignee=checked_assignee(draft.workspace_id, draft.assignee),
    )


def _chat_of(draft: NewTask) -> ChatOrigin | None:
    """The draft's chat source, checked; only a workspace's task comes from a chat."""
    if draft.chat is None:
        return None
    if draft.workspace_id is None:
        raise TaskRuleError(TaskRule.INVALID)
    return checked_origin(draft.chat)


def _chat_columns(chat: ChatOrigin | None) -> dict[str, object]:
    """The task row's columns of its chat source."""
    if chat is None:
        return {}
    return {
        "source_chat_connection_id": chat.connection_id,
        "source_chat_messenger": chat.messenger.value,
        "source_chat_title": chat.chat_title,
        "source_chat_message_url": chat.message_url,
        "source_chat_message_at": chat.message_at,
    }
