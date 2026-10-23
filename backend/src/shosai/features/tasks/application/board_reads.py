"""A person's boards and one board with its cards (tasks plan §3.3, §3.5 flow 2, §3.14).

A board shows its open cards and those done within 30 days (TK-D5) that its person may
still read; the count of a board is the same set. A read first sets the board right
(`landing`), under the board's lock, so the cards come in their settled order. The cards'
names, spaces, counts, covers, values and time fields are read once for the whole board, and
the covers' preview links are signed after the read's transaction closes.
"""

from collections import defaultdict
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any, Final
from uuid import UUID

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import Principal
from shosai.features.tasks.application.attachment_views import with_cover_previews
from shosai.features.tasks.application.board_access import (
    board_and_incoming,
    incoming_board,
    owned_board,
    shown,
)
from shosai.features.tasks.application.board_views import (
    BoardDetailView,
    BoardSummaryView,
    BoardsView,
    PlacedCard,
    column_of,
)
from shosai.features.tasks.application.landing import reconcile, waiting_for
from shosai.features.tasks.application.part_reads import counted_columns, counted_of
from shosai.features.tasks.application.placements import lock_board
from shosai.features.tasks.application.sticker_views import card_values_json, values_of
from shosai.features.tasks.application.task_parts import CardRecord
from shosai.features.tasks.application.views import CardView, Wanted, card_of, context_of
from shosai.features.tasks.domain.boards import BoardIcon
from shosai.features.tasks.domain.placement import BoardColumn
from shosai.features.tasks.domain.tasks import TaskStatus
from shosai.features.tasks.infrastructure.board_records import (
    BoardColumnRecord,
    BoardRecord,
    TaskPlacementRecord,
)
from shosai.features.tasks.infrastructure.task_records import TASK_RESOURCE, TaskRecord
from shosai.features.workspaces.contracts import ACCESS_POLICY, Viewer

PLACED = TaskPlacementRecord
CARD_COLUMNS: Final = (
    TaskRecord.id, TaskRecord.user_id, TaskRecord.org_id, TaskRecord.title, TaskRecord.status,
    TaskRecord.priority, TaskRecord.starts_on, TaskRecord.due_on, TaskRecord.assignee_user_id,
    TaskRecord.assignee_name, TaskRecord.recurrence, TaskRecord.leo_fields, TaskRecord.source,
    TaskRecord.cover_attachment_id, TaskRecord.stopwatch_since, TaskRecord.stopwatch_total_ms,
    TaskRecord.stopwatch_by_column, TaskRecord.timer_length_ms, TaskRecord.timer_ends_at,
    TaskRecord.timer_paused_left_ms, TaskRecord.plan_minutes, TaskRecord.fact_minutes,
)  # fmt: skip


class BoardReads:
    """Reads the person's boards, setting each right first."""

    def __init__(
        self,
        transactions: HomeTransactions,
        ports: PortDirectory,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._ports = ports
        self._clock = clock

    def readable(self, viewer: UUID) -> ColumnElement[bool]:
        """The tasks the person may read now."""
        return self._ports.get(ACCESS_POLICY).readable(TASK_RESOURCE, Viewer(viewer))

    async def boards(self, principal: Principal) -> BoardsView:
        """The person's boards, the incoming board landed first."""
        viewer, now = principal.user_id, self._clock()
        async with self._transactions.begin(principal.scope()) as session:
            incoming = await incoming_board(session, viewer)
            if incoming is not None:
                await lock_board(session, incoming)
                await reconcile(session, viewer, (incoming, True), (self.readable(viewer), now))
            return await self.listing(session, viewer, now)

    async def listing(self, session: AsyncSession, viewer: UUID, now: datetime) -> BoardsView:
        """The boards with their counts and the waiting incoming work, as they are."""
        boards = list(
            await session.scalars(
                select(BoardRecord)
                .where(BoardRecord.user_id == viewer)
                .order_by(BoardRecord.created_at, BoardRecord.id)
            )
        )
        incoming = await incoming_board(session, viewer)
        counts = await self._counts(session, viewer, now)
        waiting = await session.scalar(
            select(func.count())
            .select_from(TaskRecord)
            .where(self.readable(viewer), waiting_for(viewer))
        )
        items = tuple(summary_of(board, incoming, counts.get(board.id, 0)) for board in boards)
        return BoardsView(items, incoming, waiting or 0)

    async def owned(self, principal: Principal, board_id: UUID) -> None:
        """Whether the board is the person's; 404 otherwise."""
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            await owned_board(session, principal.user_id, board_id)

    async def detail(self, principal: Principal, board_id: UUID) -> BoardDetailView:
        """The board with its cards, set right first.

        Four statements when nothing moves — the transaction's settings, the board with the
        person's incoming choice under its lock, the columns, the cards with their counts and
        covers — as a Russian home is a 45 ms round trip from the plane (§3.11).
        """
        viewer, now = principal.user_id, self._clock()
        async with self._transactions.begin(principal.scope()) as session:
            board, incoming, stickers = await board_and_incoming(session, viewer, board_id)
            columns = list(
                await session.scalars(
                    select(BoardColumnRecord)
                    .where(BoardColumnRecord.board_id == board_id)
                    .order_by(BoardColumnRecord.position)
                )
            )
            rows = await self._cards(session, viewer, board_id, now)
            known = (
                [BoardColumn(c.id, TaskStatus(c.kind), c.position) for c in columns],
                [(row.task.id, row.column_id, TaskStatus(row.task.status)) for row in rows],
            )
            rules = (self.readable(viewer), now)
            if await reconcile(session, viewer, (board_id, incoming), rules, known):
                await session.refresh(board)
                rows = await self._cards(session, viewer, board_id, now)
            view = await self._view(session, viewer, (board, incoming, columns), (rows, now))
            view = replace(view, stickers=tuple(stickers))
        signed = iter(
            await with_cover_previews(
                self._ports, principal.scope(), [card for c in view.columns for card in c.cards]
            )
        )
        laid = tuple(
            replace(column, cards=tuple(next(signed) for _ in column.cards))
            for column in view.columns
        )
        return replace(view, columns=laid)

    async def _cards(
        self, session: AsyncSession, viewer: UUID, board_id: UUID, now: datetime
    ) -> list[PlacedCard]:
        """The board's shown cards in order, each with its column, counts and cover."""
        # Только поля карточки, строками, без учёта объектов ORM: у тысячи задач это заметно.
        rows = await session.execute(
            select(*CARD_COLUMNS, PLACED.column_id, *counted_columns(), card_values_json(board_id))
            .join(PLACED, PLACED.task_id == TaskRecord.id)
            .where(
                PLACED.user_id == viewer, PLACED.board_id == board_id,
                self.readable(viewer), shown(now),
            )
            .order_by(PLACED.rank)
        )  # fmt: skip
        placed: list[PlacedCard] = []
        width = len(CARD_COLUMNS)
        for row in rows:
            fields: tuple[Any, ...] = tuple(row)
            card = CardRecord(*fields[:width])
            column_id, done, total, comments, files, held, values = fields[width:]
            counted = counted_of((done, total, comments, files, held))
            placed.append(PlacedCard(card, column_id, counted, values_of(values)))
        return placed

    async def _view(
        self,
        session: AsyncSession,
        viewer: UUID,
        board: tuple[BoardRecord, bool, list[BoardColumnRecord]],
        cards: tuple[list[PlacedCard], datetime],
    ) -> BoardDetailView:
        record, incoming, columns = board
        rows, now = cards
        counted = {row.task.id: row.counted for row in rows}
        tasks = [row.task for row in rows]
        context = await context_of(session, self._ports, viewer, tasks, Wanted(counted=counted))
        placed: defaultdict[UUID, list[CardView]] = defaultdict(list)
        for row in rows:
            card = card_of(row.task, viewer, context)
            placed[row.column_id].append(replace(card, values=row.values))
        heads = tuple(column_of(column, placed[column.id]) for column in columns)
        summary = summary_of(record, record.id if incoming else None, len(rows))
        return BoardDetailView(summary, heads, record.revision, now)

    async def _counts(self, session: AsyncSession, viewer: UUID, now: datetime) -> dict[UUID, int]:
        rows = await session.execute(
            select(PLACED.board_id, func.count())
            .join(TaskRecord, TaskRecord.id == PLACED.task_id)
            .where(PLACED.user_id == viewer, self.readable(viewer), shown(now))
            .group_by(PLACED.board_id)
        )
        return {board_id: count for board_id, count in rows}


def summary_of(board: BoardRecord, incoming: UUID | None, task_count: int) -> BoardSummaryView:
    """A board's summary."""
    return BoardSummaryView(
        board.id, board.name, BoardIcon(board.icon), board.id == incoming, task_count,
        board.created_at,
    )  # fmt: skip
