"""Reaching a person's board: its row under its lock, their incoming board, what it shows.

A board is only its person's: another's or an unknown one is `board_not_found`. The board
read takes the row, the incoming board and the board's own stickers in one statement. The
incoming board is the one the person chose, else their first board: no task stays off every
board while the person has one (the owner's rule of 2026-10-28, amending TK-D4).
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import ColumnElement, ScalarSelect, case, exists, false, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.features.tasks.application.sticker_views import (
    BoardStickerView,
    board_stickers_json,
    stickers_of,
    system_stickers,
)
from shosai.features.tasks.contracts import BoardNotFoundError
from shosai.features.tasks.domain.boards import DONE_VISIBLE
from shosai.features.tasks.domain.tasks import TaskStatus
from shosai.features.tasks.infrastructure.board_records import BoardRecord, TaskSettingsRecord
from shosai.features.tasks.infrastructure.task_records import TaskRecord


def shown(now: datetime) -> ColumnElement[bool]:
    """The cards a board shows: open, or done within the last 30 days."""
    return or_(
        TaskRecord.status != TaskStatus.DONE.value, TaskRecord.completed_at >= now - DONE_VISIBLE
    )


def incoming_of(viewer: UUID) -> ScalarSelect[UUID | None]:
    """The person's incoming board as one expression: the chosen one, else their first."""
    chosen = (
        select(TaskSettingsRecord.incoming_board_id)
        .where(TaskSettingsRecord.user_id == viewer)
        .scalar_subquery()
    )
    first = (
        select(BoardRecord.id)
        .where(BoardRecord.user_id == viewer)
        .order_by(BoardRecord.created_at, BoardRecord.id)
        .limit(1)
        .scalar_subquery()
    )
    return select(func.coalesce(chosen, first)).scalar_subquery()


async def incoming_board(session: AsyncSession, viewer: UUID) -> UUID | None:
    """The person's incoming board: the one they chose, else their first; none without one."""
    found: UUID | None = await session.scalar(select(incoming_of(viewer)))
    return found


async def owned_board(
    session: AsyncSession, viewer: UUID, board_id: UUID, *, lock: bool = False
) -> BoardRecord:
    """The person's board, locked when asked; 404 otherwise."""
    statement = select(BoardRecord).where(BoardRecord.id == board_id, BoardRecord.user_id == viewer)
    board = await session.scalar(statement.with_for_update() if lock else statement)
    if board is None:
        raise BoardNotFoundError
    return board


async def board_and_incoming(
    session: AsyncSession, viewer: UUID, board_id: UUID, waits: ColumnElement[bool]
) -> tuple[BoardRecord, bool, bool, list[BoardStickerView]]:
    """The person's board under its lock, whether it is their incoming board, whether a task
    `waits` for it there, and its stickers, in one statement; 404."""
    incoming = incoming_of(viewer)
    waiting = case((incoming == board_id, exists().where(waits)), else_=false())
    found = (
        await session.execute(
            select(BoardRecord, incoming, waiting, board_stickers_json(BoardRecord.id))
            .where(BoardRecord.id == board_id, BoardRecord.user_id == viewer)
            .with_for_update(of=BoardRecord)
        )
    ).first()
    if found is None:
        raise BoardNotFoundError
    board, chosen, landing, own = found
    placed = system_stickers(board.system_stickers, board.stopwatch_automations)
    return board, chosen == board_id, bool(landing), [*placed, *stickers_of(own)]
