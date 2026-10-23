"""Putting a card in a column of a person's board, in order (§3.5 flow 3).

Writes to one board take the board's row lock first, so concurrent moves and inserts are
ordered and no two cards share a place. A card's key lies between its neighbours; when a key
grows past its bound the column gets evenly spaced keys again, in the same transaction.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.features.tasks.domain.ranks import needs_rebalance, rank_at, rank_between, spaced_ranks
from shosai.features.tasks.domain.tasks import TaskStatus
from shosai.features.tasks.infrastructure.board_records import (
    BoardColumnRecord,
    BoardRecord,
    TaskPlacementRecord,
)


async def lock_board(session: AsyncSession, board_id: UUID) -> None:
    """Take the board's row lock: writes to one board go one after another."""
    await session.execute(
        select(BoardRecord.id).where(BoardRecord.id == board_id).with_for_update()
    )


async def first_column_of(session: AsyncSession, board_id: UUID, kind: TaskStatus) -> UUID | None:
    """The leftmost column of this kind on the board."""
    found: UUID | None = await session.scalar(
        select(BoardColumnRecord.id)
        .where(BoardColumnRecord.board_id == board_id, BoardColumnRecord.kind == kind.value)
        .order_by(BoardColumnRecord.position)
        .limit(1)
    )
    return found


async def column_cards(
    session: AsyncSession, board_id: UUID, column_id: UUID
) -> list[tuple[UUID, str]]:
    """The column's cards with their keys, in order."""
    rows = await session.execute(
        select(TaskPlacementRecord.task_id, TaskPlacementRecord.rank)
        .where(TaskPlacementRecord.board_id == board_id, TaskPlacementRecord.column_id == column_id)
        .order_by(TaskPlacementRecord.rank)
    )
    return [(task_id, rank) for task_id, rank in rows]


@dataclass(frozen=True, slots=True)
class CardSpot:
    """Where a card goes: a board, one of its columns and a position in it, 0 the top."""

    board_id: UUID
    column_id: UUID
    position: int


async def place(
    session: AsyncSession, viewer: UUID, task_id: UUID, spot: CardSpot, now: datetime
) -> None:
    """Put the task at its spot under the board's lock; a column too dense is spaced again."""
    await lock_board(session, spot.board_id)
    cards = await column_cards(session, spot.board_id, spot.column_id)
    others = [card for card in cards if card[0] != task_id]
    rank = rank_at([key for _, key in others], spot.position)
    if needs_rebalance(rank):
        order = [task for task, _ in others]
        order.insert(min(max(spot.position, 0), len(order)), task_id)
        await _respace(session, spot, order)
        rank = dict(zip(order, spaced_ranks(len(order)), strict=True))[task_id]
    placed = await session.get(TaskPlacementRecord, (viewer, task_id))
    if placed is None:
        session.add(
            TaskPlacementRecord(
                user_id=viewer,
                task_id=task_id,
                board_id=spot.board_id,
                column_id=spot.column_id,
                rank=rank,
                placed_at=now,
            )
        )
    else:
        placed.board_id, placed.column_id, placed.rank, placed.placed_at = (
            spot.board_id,
            spot.column_id,
            rank,
            now,
        )
    await session.flush()


async def _respace(session: AsyncSession, spot: CardSpot, order: list[UUID]) -> None:
    keys = dict(zip(order, spaced_ranks(len(order)), strict=True))
    for task_id, key in keys.items():
        await session.execute(
            update(TaskPlacementRecord)
            .where(
                TaskPlacementRecord.board_id == spot.board_id,
                TaskPlacementRecord.column_id == spot.column_id,
                TaskPlacementRecord.task_id == task_id,
            )
            .values(rank=key)
        )


async def put_on_top(
    session: AsyncSession, viewer: UUID, spot: CardSpot, task_ids: Sequence[UUID], now: datetime
) -> None:
    """Put the tasks on top of the column, the first of them topmost, in one pass: keys
    above the column's first card, the column spaced again when they grow too long."""
    if not task_ids:
        return
    moving = set(task_ids)
    cards = await column_cards(session, spot.board_id, spot.column_id)
    others = [card for card in cards if card[0] not in moving]
    keys: dict[UUID, str] = {}
    above = others[0][1] if others else None
    for task_id in reversed(task_ids):
        above = keys[task_id] = rank_between(None, above)
    if any(needs_rebalance(key) for key in keys.values()):
        order = [*task_ids, *(task for task, _ in others)]
        keys = dict(zip(order, spaced_ranks(len(order)), strict=True))
        for task_id, key in keys.items():
            if task_id not in moving:
                await _set_rank(session, spot, task_id, key)
    for task_id in task_ids:
        await _put(session, viewer, task_id, spot, (keys[task_id], now))
    await session.flush()


async def _put(
    session: AsyncSession, viewer: UUID, task_id: UUID, spot: CardSpot, at: tuple[str, datetime]
) -> None:
    rank, now = at
    placed = await session.get(TaskPlacementRecord, (viewer, task_id))
    if placed is None:
        session.add(
            TaskPlacementRecord(
                user_id=viewer, task_id=task_id, board_id=spot.board_id,
                column_id=spot.column_id, rank=rank, placed_at=now,
            )
        )  # fmt: skip
        return
    placed.board_id, placed.column_id, placed.rank, placed.placed_at = (
        spot.board_id, spot.column_id, rank, now,
    )  # fmt: skip


async def _set_rank(session: AsyncSession, spot: CardSpot, task_id: UUID, key: str) -> None:
    await session.execute(
        update(TaskPlacementRecord)
        .where(
            TaskPlacementRecord.board_id == spot.board_id,
            TaskPlacementRecord.column_id == spot.column_id,
            TaskPlacementRecord.task_id == task_id,
        )
        .values(rank=key)
    )
