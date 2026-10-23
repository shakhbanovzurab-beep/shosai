"""A task's values as its panel shows them (tasks plan §3.15).

The values of the stickers on the board the task sits on for the reader show on its card;
the rest come as `other_values`, each with its sticker's definition and nothing else of the
sticker's owner. A task on none of the reader's boards shows them all as others.
"""

from dataclasses import replace
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.features.tasks.application.sticker_views import split_values, task_values
from shosai.features.tasks.application.views import TaskView
from shosai.features.tasks.infrastructure.sticker_records import BoardStickerRecord


async def with_values(session: AsyncSession, view: TaskView) -> TaskView:
    """The task with its values split by the reader's board."""
    values = await task_values(session, view.card.id)
    if not values:
        return view
    on_board: set[UUID] = set()
    if view.placement is not None:
        on_board = set(
            await session.scalars(
                select(BoardStickerRecord.sticker_id).where(
                    BoardStickerRecord.board_id == view.placement[0]
                )
            )
        )
    shown, others = split_values(values, on_board)
    return replace(view, card=replace(view.card, values=shown), other_values=others)
