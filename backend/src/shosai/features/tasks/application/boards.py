"""A person's boards: made from a template, renamed, laid out, chosen as incoming, deleted
(tasks plan §3.3, TK-D4, TK-D6, §3.14).

A board is made with its template's columns in the request's language; a person holds 50,
counted under their settings row's lock so two tabs cannot pass the limit. A layout only
reorders and renames what the board shows; anything else is `board_changed`. Deleting a
board removes its placements and the hand-made personal tasks on it, with their events and
their attachments given back to files; tasks of meetings and workspaces stay.
"""

from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from http import HTTPStatus
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.events.outbox import EventOutbox
from shosai.core.i18n.locales import normalize_language
from shosai.core.kernel.errors import AppError
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import ACCOUNT_PROFILE_READER, Principal
from shosai.features.tasks.application.attachment_releases import AttachmentReleases
from shosai.features.tasks.application.board_access import incoming_board, owned_board, shown
from shosai.features.tasks.application.board_edits import (
    board_changed,
    board_deleted,
    board_made,
    incoming_chosen,
)
from shosai.features.tasks.application.board_reads import BoardReads, summary_of
from shosai.features.tasks.application.board_views import BoardSummaryView, BoardsView
from shosai.features.tasks.domain.boards import (
    BoardIcon,
    BoardRuleError,
    BoardTemplate,
    LayoutColumn,
    ShownColumn,
    checked_layout,
)
from shosai.features.tasks.domain.ranks import spaced_ranks
from shosai.features.tasks.infrastructure.board_records import (
    BoardColumnRecord,
    TaskPlacementRecord,
)
from shosai.features.tasks.infrastructure.task_records import TaskRecord

PLACED = TaskPlacementRecord
FULL_CODES = frozenset({"boards_full", "board_columns_full", "board_full", "last_column_of_kind"})


def board_failure(error: BoardRuleError) -> AppError:
    """A broken rule of boards as the API answers it: a limit or a stale layout is a conflict."""
    conflict = error.code in FULL_CODES or error.code == "board_changed"
    status = HTTPStatus.CONFLICT if conflict else HTTPStatus.UNPROCESSABLE_CONTENT
    return AppError(error.code, status)


class BoardWrites:
    """Makes, changes, lays out and deletes the person's boards."""

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
        self._reads = BoardReads(transactions, ports, clock)
        self._releases = AttachmentReleases(transactions, ports)

    async def create(
        self, principal: Principal, made: tuple[str, BoardIcon, BoardTemplate], language: str | None
    ) -> BoardSummaryView:
        """A new board with its template's columns named in the request's language, else the
        profile's, else English."""
        viewer, now = principal.user_id, self._clock()
        try:
            async with self._transactions.begin(principal.scope()) as session:
                if language is None:
                    profile = await self._ports.get(ACCOUNT_PROFILE_READER).profile(session, viewer)
                    language = None if profile is None else normalize_language(profile.language)
                board = await board_made(session, viewer, made, (language, now))
                return summary_of(board, await incoming_board(session, viewer), 0)
        except BoardRuleError as error:
            raise board_failure(error) from error

    async def change(
        self, principal: Principal, board_id: UUID, change: tuple[str | None, BoardIcon | None]
    ) -> BoardSummaryView:
        """The board renamed or with another icon."""
        viewer, now = principal.user_id, self._clock()
        try:
            async with self._transactions.begin(principal.scope()) as session:
                await board_changed(session, viewer, board_id, (*change, now))
                listing = await self._reads.listing(session, viewer, now)
        except BoardRuleError as error:
            raise board_failure(error) from error
        return next(item for item in listing.items if item.id == board_id)

    async def delete(self, principal: Principal, board_id: UUID) -> None:
        """Delete the board and the hand-made personal tasks on it (TK-D6)."""
        async with self._transactions.begin(principal.scope()) as session:
            await board_deleted(session, self._outbox, principal.user_id, board_id)
        await self._releases.owner(principal.scope())

    async def set_incoming(self, principal: Principal, board_id: UUID | None) -> BoardsView:
        """Choose the board incoming work lands on, or none; what waits lands at once."""
        viewer, now = principal.user_id, self._clock()
        async with self._transactions.begin(principal.scope()) as session:
            await incoming_chosen(session, viewer, board_id, (self._reads.readable(viewer), now))
            return await self._reads.listing(session, viewer, now)

    async def lay_out(
        self, principal: Principal, board_id: UUID, layout: Sequence[LayoutColumn]
    ) -> None:
        """Reorder and rename the board's columns and cards, if they are the ones it shows."""
        viewer, now = principal.user_id, self._clock()
        async with self._transactions.begin(principal.scope()) as session:
            board = await owned_board(session, viewer, board_id, lock=True)
            placed = await self._placed(session, viewer, board_id, now)
            try:
                checked = checked_layout(
                    [
                        ShownColumn(column_id, tuple(cards[0]))
                        for column_id, cards in placed.items()
                    ],
                    layout,
                )
            except BoardRuleError as error:
                raise board_failure(error) from error
            await _apply_layout(session, checked, placed)
            board.revision += 1
            board.updated_at = now

    async def _placed(
        self, session: AsyncSession, viewer: UUID, board_id: UUID, now: datetime
    ) -> dict[UUID, tuple[list[UUID], list[UUID]]]:
        """Each column's shown cards and the rest, in their order."""
        columns = await session.scalars(
            select(BoardColumnRecord.id)
            .where(BoardColumnRecord.board_id == board_id)
            .order_by(BoardColumnRecord.position)
        )
        placed: dict[UUID, tuple[list[UUID], list[UUID]]] = {c: ([], []) for c in columns}
        visible = select(TaskRecord.id).where(self._reads.readable(viewer), shown(now))
        rows = await session.execute(
            select(PLACED.column_id, PLACED.task_id, PLACED.task_id.in_(visible))
            .where(PLACED.user_id == viewer, PLACED.board_id == board_id)
            .order_by(PLACED.rank)
        )
        for column_id, task_id, seen in rows:
            placed[column_id][0 if seen else 1].append(task_id)
        return placed


async def _apply_layout(
    session: AsyncSession,
    layout: Sequence[LayoutColumn],
    placed: dict[UUID, tuple[list[UUID], list[UUID]]],
) -> None:
    """Columns in the layout's order and titles, each one's cards spaced in the new order with
    the cards it does not show after them."""
    for position, column in enumerate(layout):
        await session.execute(
            update(BoardColumnRecord)
            .where(BoardColumnRecord.id == column.column_id)
            .values(position=position, title=column.title)
        )
        order = [*column.task_ids, *placed[column.column_id][1]]
        for task_id, rank in zip(order, spaced_ranks(len(order)), strict=True):
            await session.execute(
                update(PLACED)
                .where(PLACED.column_id == column.column_id, PLACED.task_id == task_id)
                .values(rank=rank)
            )
