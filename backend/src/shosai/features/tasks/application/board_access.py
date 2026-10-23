"""Reaching a person's board: its row under its lock, their incoming choice, what it shows.

A board is only its person's: another's or an unknown one is `board_not_found`. The board
read takes the row, the incoming choice and the board's own stickers in one statement.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import ColumnElement, or_, select
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


async def incoming_board(session: AsyncSession, viewer: UUID) -> UUID | None:
    """The person's incoming board, if they chose one."""
    found: UUID | None = await session.scalar(
        select(TaskSettingsRecord.incoming_board_id).where(TaskSettingsRecord.user_id == viewer)
    )
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
    session: AsyncSession, viewer: UUID, board_id: UUID
) -> tuple[BoardRecord, bool, list[BoardStickerView]]:
    """The person's board under its lock, whether it is their incoming board, and its
    stickers, in one statement; 404."""
    chosen = (
        select(TaskSettingsRecord.incoming_board_id)
        .where(TaskSettingsRecord.user_id == viewer)
        .scalar_subquery()
    )
    found = (
        await session.execute(
            select(BoardRecord, chosen, board_stickers_json(BoardRecord.id))
            .where(BoardRecord.id == board_id, BoardRecord.user_id == viewer)
            .with_for_update(of=BoardRecord)
        )
    ).first()
    if found is None:
        raise BoardNotFoundError
    board, incoming, own = found
    placed = system_stickers(board.system_stickers, board.stopwatch_automations)
    return board, incoming == board_id, [*placed, *stickers_of(own)]
