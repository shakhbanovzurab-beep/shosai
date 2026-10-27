"""A board's columns: added, changed and removed without losing a card (TK-D12, KG-D9; §3.14).

Every write takes the board's lock. A board holds 20 columns; a new one goes to its
position, the others making room. A column's colour and collapse are the person's view. A
removed column's cards go on top of the first other column of its kind, in their order;
the last column of a kind stays, so a task of any status has a place.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from http import HTTPStatus
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.ids import new_id
from shosai.features.identity.contracts import Principal
from shosai.features.tasks.application.board_access import owned_board
from shosai.features.tasks.application.board_views import ColumnView, column_of
from shosai.features.tasks.application.boards import board_failure
from shosai.features.tasks.application.placements import CardSpot, column_cards, put_on_top
from shosai.features.tasks.domain.board_fields import Color
from shosai.features.tasks.domain.boards import (
    BoardRule,
    BoardRuleError,
    check_column_room,
    checked_column_title,
)
from shosai.features.tasks.domain.tasks import TaskStatus
from shosai.features.tasks.infrastructure.board_records import BoardColumnRecord, BoardRecord

COLUMNS = BoardColumnRecord


@dataclass(frozen=True, slots=True)
class NewColumn:
    """A column to add."""

    title: str
    kind: TaskStatus
    position: int
    color: Color | None = None


@dataclass(frozen=True, slots=True)
class ColumnChange:
    """What a change of a column sets; a field left as `None` stays, but the colour, which
    `color_sent` says was sent (`null` removes it)."""

    title: str | None = None
    color: Color | None = None
    color_sent: bool = False
    collapsed: bool | None = None
    position: int | None = None


def not_found() -> AppError:
    """No such column of the board."""
    return AppError("column_not_found", HTTPStatus.NOT_FOUND)


class Columns:
    """Adds, changes and removes a board's columns."""

    def __init__(
        self,
        transactions: HomeTransactions,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._clock = clock

    async def create(self, principal: Principal, board_id: UUID, new: NewColumn) -> ColumnView:
        """The new column at its position, the end past it."""
        try:
            async with self._transactions.begin(principal.scope()) as session:
                column = await column_added(
                    session, principal.user_id, (board_id, new), self._clock()
                )
                return column_of(column)
        except BoardRuleError as error:
            raise board_failure(error) from error

    async def change(
        self, principal: Principal, board_id: UUID, column_id: UUID, change: ColumnChange
    ) -> ColumnView:
        """The column renamed, recoloured, collapsed or moved."""
        try:
            async with self._transactions.begin(principal.scope()) as session:
                column = await column_changed(
                    session, principal.user_id, (board_id, column_id, change), self._clock()
                )
                return column_of(column)
        except BoardRuleError as error:
            raise board_failure(error) from error

    async def delete(self, principal: Principal, board_id: UUID, column_id: UUID) -> None:
        """Remove the column; its cards go on top of the next column of its kind."""
        try:
            async with self._transactions.begin(principal.scope()) as session:
                await column_removed(
                    session, principal.user_id, (board_id, column_id), self._clock()
                )
        except BoardRuleError as error:
            raise board_failure(error) from error


async def column_added(
    session: AsyncSession, viewer: UUID, adding: tuple[UUID, NewColumn], now: datetime
) -> BoardColumnRecord:
    """The new column at its position in the caller's transaction; `BoardRuleError` past the
    rules."""
    board_id, new = adding
    title = checked_column_title(new.title)
    board = await owned_board(session, viewer, board_id, lock=True)
    order = await _columns(session, board_id)
    check_column_room(len(order))
    column = COLUMNS(
        id=new_id(), board_id=board_id, user_id=viewer, title=title, kind=new.kind.value,
        position=len(order), color=None if new.color is None else new.color.value,
        collapsed=False,
    )  # fmt: skip
    session.add(column)
    await session.flush()
    order.insert(min(max(new.position, 0), len(order)), column)
    await _arrange(session, order)
    _touched(board, now)
    return column


async def column_changed(
    session: AsyncSession,
    viewer: UUID,
    changing: tuple[UUID, UUID, ColumnChange],
    now: datetime,
) -> BoardColumnRecord:
    """The column renamed, recoloured, collapsed or moved in the caller's transaction."""
    board_id, column_id, change = changing
    title = None if change.title is None else checked_column_title(change.title)
    board = await owned_board(session, viewer, board_id, lock=True)
    order = await _columns(session, board_id)
    column = next((found for found in order if found.id == column_id), None)
    if column is None:
        raise not_found()
    column.title = title or column.title
    if change.color_sent:
        column.color = None if change.color is None else change.color.value
    if change.collapsed is not None:
        column.collapsed = change.collapsed
    if change.position is not None:
        order.remove(column)
        order.insert(min(max(change.position, 0), len(order)), column)
        await _arrange(session, order)
    _touched(board, now)
    await session.flush()
    return column


async def column_removed(
    session: AsyncSession, viewer: UUID, removing: tuple[UUID, UUID], now: datetime
) -> None:
    """Remove the column in the caller's transaction; its cards go on top of the next column
    of its kind, and the last column of a kind stays (`BoardRuleError`)."""
    board_id, column_id = removing
    board = await owned_board(session, viewer, board_id, lock=True)
    order = await _columns(session, board_id)
    column = next((found for found in order if found.id == column_id), None)
    if column is None:
        raise not_found()
    heir = next((c for c in order if c.id != column_id and c.kind == column.kind), None)
    if heir is None:
        raise BoardRuleError(BoardRule.LAST_COLUMN_OF_KIND)
    cards = [task_id for task_id, _ in await column_cards(session, board_id, column_id)]
    await put_on_top(session, viewer, CardSpot(board_id, heir.id, 0), cards, now)
    await session.delete(column)
    await session.flush()
    order.remove(column)
    await _arrange(session, order)
    _touched(board, now)


async def _columns(session: AsyncSession, board_id: UUID) -> list[BoardColumnRecord]:
    found = await session.scalars(
        select(COLUMNS).where(COLUMNS.board_id == board_id).order_by(COLUMNS.position)
    )
    return list(found)


async def _arrange(session: AsyncSession, order: list[BoardColumnRecord]) -> None:
    """Number the columns from the left; positions are unique at commit."""
    for position, column in enumerate(order):
        if column.position != position:
            await session.execute(
                update(COLUMNS).where(COLUMNS.id == column.id).values(position=position)
            )
            column.position = position


def _touched(board: BoardRecord, now: datetime) -> None:
    board.revision += 1
    board.updated_at = now
