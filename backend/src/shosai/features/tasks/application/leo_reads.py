"""What Leo reads of tasks: a search and one board, as the person may read them (step 7).

Both run in a read-only transaction under the person's scope, inside workspaces' access
policy, so a task the person may not read is never found (inv-14). The person's today is
their day in their profile's zone. A board's read writes nothing: it shows each card in the
column its status puts it in, as the board's own next read would, without landing incoming
work or raising a revision; it holds open cards and those done in the last 30 days.
"""

from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum
from typing import Final
from uuid import UUID

from sqlalchemy import ColumnElement, and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.tasks.application.board_access import incoming_board, shown
from shosai.features.tasks.application.landing import landing_spots
from shosai.features.tasks.application.placements import board_columns
from shosai.features.tasks.application.task_query import OPEN, StatusFilter, TaskQuery, filters_of
from shosai.features.tasks.application.task_reads import zone_of
from shosai.features.tasks.application.views import WITH_PLACEMENTS, TaskView, context_of, task_of
from shosai.features.tasks.domain.placement import spot_for
from shosai.features.tasks.domain.tasks import TaskStatus
from shosai.features.tasks.infrastructure.board_records import (
    BoardColumnRecord,
    BoardRecord,
    TaskPlacementRecord,
)
from shosai.features.tasks.infrastructure.task_records import TASK_RESOURCE, TaskRecord
from shosai.features.workspaces.contracts import ACCESS_POLICY, Viewer

PLACED = TaskPlacementRecord
# На доске Лео видит первые карточки каждой колонки, всего не больше стольких.
BOARD_CARDS: Final = 60
DUE_LAST: Final = TaskRecord.due_on.is_(None)


class DueWindow(StrEnum):
    """Which due days to find, in the user's day."""

    OVERDUE = "overdue"
    TODAY = "today"
    THIS_WEEK = "this_week"


@dataclass(frozen=True, slots=True)
class TaskSearch:
    """What Leo looks for; each filter given narrows the result."""

    text: str | None = None
    status: StatusFilter | None = None
    due: DueWindow | None = None
    workspace_id: UUID | None = None
    personal: bool = False
    meeting_id: UUID | None = None
    board_id: UUID | None = None
    mine: bool = False
    limit: int = 10


@dataclass(frozen=True, slots=True)
class Found:
    """Tasks found, the person's today and where their cards sit, by board and column."""

    tasks: tuple[TaskView, ...]
    more: bool
    today: date
    boards: dict[UUID, str] = field(default_factory=dict)
    columns: dict[UUID, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class BoardColumnView:
    """A column with its first cards and how many more it holds."""

    title: str
    kind: TaskStatus
    cards: tuple[TaskView, ...]
    more: int


@dataclass(frozen=True, slots=True)
class BoardRead:
    """A board as Leo reads it, and the person's other boards."""

    board_id: UUID
    name: str
    columns: tuple[BoardColumnView, ...]
    others: tuple[tuple[UUID, str], ...]


class LeoReads:
    """Reads tasks for Leo's tools."""

    def __init__(
        self,
        transactions: HomeTransactions,
        ports: PortDirectory,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._ports = ports
        self._clock = clock

    def _readable(self, viewer: UUID) -> ColumnElement[bool]:
        return self._ports.get(ACCESS_POLICY).readable(TASK_RESOURCE, Viewer(viewer))

    async def search(self, scope: TenancyScope, search: TaskSearch) -> Found:
        """The tasks found, by due day, undated last; `limit` of them at most."""
        viewer = _person(scope)
        async with self._transactions.begin(scope, read_only=True) as session:
            today = self._clock().astimezone(await zone_of(session, self._ports, viewer)).date()
            query = TaskQuery(
                workspace_id=search.workspace_id, personal=search.personal, status=search.status,
                meeting_id=search.meeting_id, text=search.text,
            )  # fmt: skip
            filters = [
                self._readable(viewer), *filters_of(query, Viewer(viewer)),
                *_due(search.due, today), *_scoped(search, viewer),
            ]  # fmt: skip
            rows = list(
                await session.scalars(
                    select(TaskRecord)
                    .where(*filters)
                    .order_by(DUE_LAST, TaskRecord.due_on, TaskRecord.created_at, TaskRecord.id)
                    .limit(search.limit + 1)
                )
            )
            more, rows = len(rows) > search.limit, rows[: search.limit]
            context = await context_of(session, self._ports, viewer, rows, WITH_PLACEMENTS)
            found = tuple(task_of(row, viewer, context) for row in rows)
            views = await _where_seen(session, viewer, found, self._readable(viewer))
            boards, columns = await _names(session, views)
        return Found(views, more, today, boards, columns)

    async def board(self, scope: TenancyScope, board_id: UUID | None) -> BoardRead | None:
        """The board, or the incoming one, else the first; None when the person has none."""
        viewer, now = _person(scope), self._clock()
        async with self._transactions.begin(scope, read_only=True) as session:
            boards = list(
                (
                    await session.execute(
                        select(BoardRecord.id, BoardRecord.name)
                        .where(BoardRecord.user_id == viewer)
                        .order_by(BoardRecord.created_at, BoardRecord.id)
                    )
                ).all()
            )
            chosen = await _chosen(session, viewer, board_id, [b for b, _ in boards])
            if chosen is None:
                return None
            columns = await board_columns(session, chosen)
            titles = dict(
                (
                    await session.execute(
                        select(BoardColumnRecord.id, BoardColumnRecord.title).where(
                            BoardColumnRecord.board_id == chosen
                        )
                    )
                ).all()
            )
            rows = (
                await session.execute(
                    select(TaskRecord, PLACED.column_id)
                    .join(PLACED, PLACED.task_id == TaskRecord.id)
                    .where(
                        PLACED.user_id == viewer, PLACED.board_id == chosen,
                        self._readable(viewer), shown(now),
                    )
                    .order_by(PLACED.rank)
                )
            ).all()  # fmt: skip
            sitting: defaultdict[UUID, list[TaskRecord]] = defaultdict(list)
            for task, column_id in rows:
                spot = spot_for(TaskStatus(task.status), columns, column_id)
                sitting[spot.column_id].append(task)
            share = max(3, BOARD_CARDS // max(len(columns), 1))
            kept = [task for column in columns for task in sitting[column.column_id][:share]]
            context = await context_of(session, self._ports, viewer, kept)
            views = {task.id: task_of(task, viewer, context) for task in kept}
        laid = tuple(
            BoardColumnView(
                titles[column.column_id], column.kind,
                tuple(views[t.id] for t in sitting[column.column_id][:share]),
                max(len(sitting[column.column_id]) - share, 0),
            )
            for column in columns
        )  # fmt: skip
        name = next(n for b, n in boards if b == chosen)
        others = tuple((b, n) for b, n in boards if b != chosen)
        return BoardRead(chosen, name, laid, others)


def _person(scope: TenancyScope) -> UUID:
    if scope.user_id is None:
        message = "инструмент Лео читает задачи только от имени человека"
        raise ValueError(message)
    return scope.user_id


def _due(due: DueWindow | None, today: date) -> list[ColumnElement[bool]]:
    if due is DueWindow.OVERDUE:
        return [TaskRecord.status.in_(OPEN), TaskRecord.due_on < today]
    if due is DueWindow.TODAY:
        return [TaskRecord.due_on == today]
    if due is DueWindow.THIS_WEEK:
        monday = today - timedelta(days=today.weekday())
        return [TaskRecord.due_on.between(monday, monday + timedelta(days=6))]
    return []


def _scoped(search: TaskSearch, viewer: UUID) -> list[ColumnElement[bool]]:
    found: list[ColumnElement[bool]] = []
    if search.board_id is not None:
        found.append(
            TaskRecord.id.in_(
                select(PLACED.task_id).where(
                    PLACED.user_id == viewer, PLACED.board_id == search.board_id
                )
            )
        )
    if search.mine:
        found.append(
            or_(
                and_(TaskRecord.org_id.is_(None), TaskRecord.user_id == viewer),
                TaskRecord.assignee_user_id == viewer,
            )
        )
    return found


async def _names(
    session: AsyncSession, views: Sequence[TaskView]
) -> tuple[dict[UUID, str], dict[UUID, str]]:
    """The names of the boards and columns the person's cards sit on."""
    placed = [view.placement for view in views if view.placement is not None]
    if not placed:
        return {}, {}
    boards = dict(
        (
            await session.execute(
                select(BoardRecord.id, BoardRecord.name).where(
                    BoardRecord.id.in_({board for board, _ in placed})
                )
            )
        ).all()
    )
    columns = dict(
        (
            await session.execute(
                select(BoardColumnRecord.id, BoardColumnRecord.title).where(
                    BoardColumnRecord.id.in_({column for _, column in placed})
                )
            )
        ).all()
    )
    return boards, columns


async def _chosen(
    session: AsyncSession, viewer: UUID, board_id: UUID | None, boards: Sequence[UUID]
) -> UUID | None:
    if board_id is not None:
        return board_id if board_id in boards else None
    incoming = await incoming_board(session, viewer)
    return incoming if incoming in boards else next(iter(boards), None)


async def _where_seen(
    session: AsyncSession,
    viewer: UUID,
    views: tuple[TaskView, ...],
    readable: ColumnElement[bool],
) -> tuple[TaskView, ...]:
    """The tasks where the person sees them: a task waiting for the incoming board where its
    next read puts it, so none reads as off every board."""
    waiting = [view.card.id for view in views if view.placement is None]
    spots = await landing_spots(session, viewer, waiting, readable)
    return tuple(
        replace(view, placement=spots[view.card.id]) if view.card.id in spots else view
        for view in views
    )
