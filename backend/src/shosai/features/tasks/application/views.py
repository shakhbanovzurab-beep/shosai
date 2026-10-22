"""Tasks as a reader sees them: the card's fields and the task's, with names and spaces (§3.8).

A task's row says who does it by id; the card names that member, names the workspace a
task belongs to, and says whether the reader may delete it — their own task, or a workspace
task they made or administer (TK-D2); a Jira task never here. What the reader needs beyond
the rows — names, workspaces, their roles, where their cards sit — is read once for a whole
list, and only when the list holds a task that needs it.
"""

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import ACCOUNT_PROFILE_READER
from shosai.features.tasks.domain.recurrence import Recurrence, recurrence_of
from shosai.features.tasks.domain.tasks import LeoField, Priority, TaskSource, TaskStatus
from shosai.features.tasks.infrastructure.board_records import TaskPlacementRecord
from shosai.features.tasks.infrastructure.task_records import TaskRecord
from shosai.features.workspaces.contracts import (
    MEMBERSHIP_READER,
    WORKSPACE_READER,
    WorkspaceFacts,
    WorkspaceRole,
)

MANAGERS = frozenset({WorkspaceRole.OWNER, WorkspaceRole.ADMIN})


@dataclass(frozen=True, slots=True)
class Who:
    """Who does a task: a member by id and name, or a name as written."""

    user_id: UUID | None
    name: str


@dataclass(frozen=True, slots=True)
class CardView:
    """What a board's card and a list's item show of a task."""

    id: UUID
    title: str
    status: TaskStatus
    priority: Priority | None
    starts_on: date | None
    due_on: date | None
    assignee: Who | None
    recurring: bool
    leo_fields: tuple[LeoField, ...]
    space: WorkspaceFacts | None
    can_delete: bool


@dataclass(frozen=True, slots=True)
class MeetingRef:
    """The meeting a task came from, while the reader may read it."""

    id: UUID
    title: str
    started_at: datetime


@dataclass(frozen=True, slots=True)
class FindingRef:
    """The moment of the meeting that proves the action item."""

    quote: str
    start_ms: int


@dataclass(frozen=True, slots=True)
class TaskView:
    """A task with what its panel shows; the meeting and its finding come with the detail."""

    card: CardView
    description: str
    recurrence: Recurrence | None
    source: TaskSource
    meeting_id: UUID | None
    finding_id: UUID | None
    project_id: UUID | None
    placement: tuple[UUID, UUID] | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    meeting: MeetingRef | None = None
    finding: FindingRef | None = None


@dataclass(frozen=True, slots=True)
class ViewContext:
    """What the views of a set of tasks need beyond their rows, for one reader."""

    names: Mapping[UUID, str]
    spaces: Mapping[UUID, WorkspaceFacts]
    roles: Mapping[UUID, WorkspaceRole]
    placements: Mapping[UUID, tuple[UUID, UUID]]


async def context_of(
    session: AsyncSession,
    ports: PortDirectory,
    viewer: UUID,
    records: Sequence[TaskRecord],
    *,
    placed: bool = False,
) -> ViewContext:
    """Read what the views need, skipping each read the tasks do not call for."""
    orgs = {record.org_id for record in records if record.org_id is not None}
    members = {record.assignee_user_id for record in records if record.assignee_user_id}
    names: Mapping[UUID, str] = {}
    if members:
        names = await ports.get(ACCOUNT_PROFILE_READER).names(session, members)
    spaces: Mapping[UUID, WorkspaceFacts] = {}
    roles: dict[UUID, WorkspaceRole] = {}
    if orgs:
        spaces = await ports.get(WORKSPACE_READER).workspaces(session, orgs)
        memberships = await ports.get(MEMBERSHIP_READER).active(session, viewer)
        roles = {membership.org_id: membership.role for membership in memberships}
    placements = await _placements(session, viewer, [r.id for r in records]) if placed else {}
    return ViewContext(names, spaces, roles, placements)


async def _placements(
    session: AsyncSession, viewer: UUID, task_ids: Collection[UUID]
) -> Mapping[UUID, tuple[UUID, UUID]]:
    if not task_ids:
        return {}
    rows = await session.execute(
        select(
            TaskPlacementRecord.task_id, TaskPlacementRecord.board_id, TaskPlacementRecord.column_id
        ).where(
            TaskPlacementRecord.user_id == viewer, TaskPlacementRecord.task_id.in_(list(task_ids))
        )
    )
    return {task_id: (board_id, column_id) for task_id, board_id, column_id in rows}


def may_delete(record: TaskRecord, viewer: UUID, roles: Mapping[UUID, WorkspaceRole]) -> bool:
    """Whether the reader may delete the task: their own, or a workspace's they made or run."""
    if record.source == TaskSource.JIRA.value:
        return False
    if record.org_id is None or record.user_id == viewer:
        return record.user_id == viewer
    return roles.get(record.org_id) in MANAGERS


def card_of(record: TaskRecord, viewer: UUID, context: ViewContext) -> CardView:
    """The card of a task for this reader."""
    return CardView(
        id=record.id,
        title=record.title,
        status=TaskStatus(record.status),
        priority=Priority(record.priority) if record.priority else None,
        starts_on=record.starts_on,
        due_on=record.due_on,
        assignee=_who(record, context),
        recurring=record.recurrence is not None,
        leo_fields=tuple(LeoField(field) for field in record.leo_fields),
        space=context.spaces.get(record.org_id) if record.org_id else None,
        can_delete=may_delete(record, viewer, context.roles),
    )


def _who(record: TaskRecord, context: ViewContext) -> Who | None:
    if record.assignee_user_id is not None:
        return Who(record.assignee_user_id, context.names.get(record.assignee_user_id, ""))
    if record.assignee_name is not None:
        return Who(None, record.assignee_name)
    return None


def task_of(record: TaskRecord, viewer: UUID, context: ViewContext) -> TaskView:
    """The task for this reader, with where their card sits."""
    return TaskView(
        card=card_of(record, viewer, context),
        description=record.description,
        recurrence=recurrence_of(record.recurrence) if record.recurrence else None,
        source=TaskSource(record.source),
        meeting_id=record.source_meeting_id,
        finding_id=record.source_finding_id,
        project_id=record.project_id,
        placement=context.placements.get(record.id),
        created_at=record.created_at,
        updated_at=record.updated_at,
        completed_at=record.completed_at,
    )
