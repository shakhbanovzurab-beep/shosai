"""The person's boards for another slice, read in the caller's transaction (`BoardReader`).

Leo's page context names the board the person is looking at, and a picker lists the boards
by name. A board is only its person's; no board syncs with Jira until Jira boards arrive
(tasks step 13), so every board reads as not synced.
"""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.features.tasks.contracts import BoardFacts
from shosai.features.tasks.infrastructure.board_records import BoardRecord


class BoardFactsReader:
    """`BoardReader`: the person's boards, by name, oldest first."""

    async def boards(self, session: AsyncSession, user_id: UUID) -> Sequence[BoardFacts]:
        """The person's boards, oldest first."""
        rows = await session.execute(
            select(BoardRecord.id, BoardRecord.name)
            .where(BoardRecord.user_id == user_id)
            .order_by(BoardRecord.created_at, BoardRecord.id)
        )
        return tuple(BoardFacts(board_id, name, synced_with_jira=False) for board_id, name in rows)

    async def exists(self, session: AsyncSession, user_id: UUID, board_id: UUID) -> bool:
        """Whether the board is the person's."""
        found = await session.scalar(
            select(BoardRecord.id).where(BoardRecord.id == board_id, BoardRecord.user_id == user_id)
        )
        return found is not None
