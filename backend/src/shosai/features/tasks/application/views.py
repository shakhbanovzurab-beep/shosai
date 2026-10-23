"""Tasks as a reader sees them: the card's fields and the task's, with names and spaces (§3.8).

A task's row says who does it by id; the card names that member, names the workspace a
task belongs to, and says whether the reader may delete it — their own task, or a workspace
task they made or administer (TK-D2); a Jira task never here. What the reader needs beyond
the rows — names, workspaces, their roles, where their cards sit, the counts of checklists,
comments and attachments, the covers — is read once for a whole list, and only when the list
holds a task that needs it.
"""

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Final
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import ACCOUNT_PROFILE_READER
from shosai.features.tasks.application.chat_views import chat_line_of, chat_origin_of
from shosai.features.tasks.application.clock_views import clocks_of
from shosai.features.tasks.application.part_reads import counts_of, covers_of
from shosai.features.tasks.application.sticker_views import StickerView
from shosai.features.tasks.application.task_parts import (
    NONE_COUNTED,
    AttachmentView,
    CardFacts,
    Counts,
    CoverRef,
    SubtaskView,
)
from shosai.features.tasks.domain.chat_source import ChatLine, ChatOrigin
from shosai.features.tasks.domain.clocks import NO_CLOCKS, TaskClocks
from shosai.features.tasks.domain.recurrence import Recurrence, recurrence_of
from shosai.features.tasks.domain.stickers import StickerValue
from shosai.features.tasks.domain.tasks import LeoField, Priority, TaskSource, TaskStatus
from shosai.features.tasks.infrastructure.board_records import TaskPlacementRecord
from shosai.features.tasks.infrastructure.id_lists import among
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
    counts: Counts = NONE_COUNTED
    cover: CoverRef | None = None
    # Значения своих полей доски, на которой лежит карточка (шаг 4s).
    values: Mapping[UUID, StickerValue] = field(default_factory=dict)
    clocks: TaskClocks = NO_CLOCKS
    source_chat: ChatLine | None = None


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
    subtasks: tuple[SubtaskView, ...] = ()
    attachments: tuple[AttachmentView, ...] = ()
    other_values: tuple[tuple[StickerView, StickerValue], ...] = ()
    chat: ChatOrigin | None = None


@dataclass(frozen=True, slots=True)
class ViewContext:
    """What the views of a set of tasks need beyond their rows, for one reader."""

    names: Mapping[UUID, str]
    spaces: Mapping[UUID, WorkspaceFacts]
    roles: Mapping[UUID, WorkspaceRole]
    placements: Mapping[UUID, tuple[UUID, UUID]]
    counts: Mapping[UUID, Counts]
    # Обложка карточки: вложение и объект files, который за ним держится.
    covers: Mapping[UUID, UUID]


@dataclass(frozen=True, slots=True)
class Wanted:
    """What a read of views takes beyond names, spaces, counts and covers: where the reader's
    cards sit, or the counts and covers its own statement already carried."""

    placed: bool = False
    counted: Mapping[UUID, tuple[Counts, UUID | None]] | None = None


NOTHING_MORE: Final = Wanted()
WITH_PLACEMENTS: Final = Wanted(placed=True)


async def context_of(
    session: AsyncSession,
    ports: PortDirectory,
    viewer: UUID,
    records: Sequence[CardFacts],
    wanted: Wanted = NOTHING_MORE,
) -> ViewContext:
    """Read what the views need, skipping each read the tasks do not call for; `counted`, when
    the caller's statement already carried the counts and covers, skips theirs.

    Nothing here writes, so the session does not flush first: with a whole board's rows in
    the identity map, every flush check would walk them all.
    """
    with session.no_autoflush:
        return await _context(session, ports, viewer, records, wanted)


async def _context(
    session: AsyncSession,
    ports: PortDirectory,
    viewer: UUID,
    records: Sequence[CardFacts],
    wanted: Wanted,
) -> ViewContext:
    members = {record.assignee_user_id for record in records if record.assignee_user_id}
    names: Mapping[UUID, str] = {}
    if members:
        names = await ports.get(ACCOUNT_PROFILE_READER).names(session, members)
    spaces, roles = await _spaces(session, ports, viewer, records)
    ids = [record.id for record in records]
    placements = await _placements(session, viewer, ids) if wanted.placed else {}
    counts, covers = await _counts(session, records, wanted.counted)
    return ViewContext(names, spaces, roles, placements, counts, covers)


async def _spaces(
    session: AsyncSession, ports: PortDirectory, viewer: UUID, records: Sequence[CardFacts]
) -> tuple[Mapping[UUID, WorkspaceFacts], Mapping[UUID, WorkspaceRole]]:
    """The workspaces of the tasks and the reader's role in each, when a task has one."""
    orgs = {record.org_id for record in records if record.org_id is not None}
    if not orgs:
        return {}, {}
    spaces = await ports.get(WORKSPACE_READER).workspaces(session, orgs)
    memberships = await ports.get(MEMBERSHIP_READER).active(session, viewer)
    return spaces, {membership.org_id: membership.role for membership in memberships}


async def _counts(
    session: AsyncSession,
    records: Sequence[CardFacts],
    counted: Mapping[UUID, tuple[Counts, UUID | None]] | None,
) -> tuple[Mapping[UUID, Counts], Mapping[UUID, UUID]]:
    """The counts and the covers' held objects: carried by the caller's rows, or read."""
    if counted is None:
        covers = [r.cover_attachment_id for r in records if r.cover_attachment_id]
        return await counts_of(session, [r.id for r in records]), await covers_of(session, covers)
    held: dict[UUID, UUID] = {}
    for record in records:
        cover = counted.get(record.id, (NONE_COUNTED, None))[1]
        if record.cover_attachment_id and cover is not None:
            held[record.cover_attachment_id] = cover
    return {task_id: found for task_id, (found, _) in counted.items()}, held


async def _placements(
    session: AsyncSession, viewer: UUID, task_ids: Collection[UUID]
) -> Mapping[UUID, tuple[UUID, UUID]]:
    if not task_ids:
        return {}
    rows = await session.execute(
        select(
            TaskPlacementRecord.task_id, TaskPlacementRecord.board_id, TaskPlacementRecord.column_id
        ).where(TaskPlacementRecord.user_id == viewer, among(TaskPlacementRecord.task_id, task_ids))
    )
    return {task_id: (board_id, column_id) for task_id, board_id, column_id in rows}


def may_delete(record: CardFacts, viewer: UUID, roles: Mapping[UUID, WorkspaceRole]) -> bool:
    """Whether the reader may delete the task: their own, or a workspace's they made or run."""
    if record.source == TaskSource.JIRA.value:
        return False
    if record.org_id is None or record.user_id == viewer:
        return record.user_id == viewer
    return roles.get(record.org_id) in MANAGERS


def card_of(record: CardFacts, viewer: UUID, context: ViewContext) -> CardView:
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
        counts=context.counts.get(record.id, NONE_COUNTED),
        cover=_cover(record, context),
        clocks=clocks_of(record),
        source_chat=chat_line_of(record),
    )


def _cover(record: CardFacts, context: ViewContext) -> CoverRef | None:
    cover = record.cover_attachment_id
    held = None if cover is None else context.covers.get(cover)
    return None if cover is None or held is None else CoverRef(cover, held)


def _who(record: CardFacts, context: ViewContext) -> Who | None:
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
        chat=chat_origin_of(record),
    )
