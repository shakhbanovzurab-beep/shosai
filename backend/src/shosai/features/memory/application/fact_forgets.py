"""Forgetting what Leo proposed to forget, after the person approved it (memory step 6).

The plan freezes the exact facts: current, the person's, in Personal or a workspace they are
in now. The card reads their statements as they are when it is drawn. The approved write ends
only those of them still current, under the row locks, in the transaction that also holds
the item's key, and each can be restored for 24 hours. It runs even if memory was switched
off after the approval: forgetting is what the person asked for, and nothing is written.
"""

from collections.abc import Callable, Collection
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.features.memory.application.fact_list import FactLists
from shosai.features.memory.application.fact_rows import FACT, fact_of, visible, write_back
from shosai.features.memory.domain.facts import RESTORE_WINDOW, EndReason, FactStatus, forget
from shosai.features.memory.infrastructure.records import MemoryFactRecord


class FactForgets:
    """Reads the facts a forget names and ends them."""

    def __init__(
        self, lists: FactLists, clock: Callable[[], datetime] = lambda: datetime.now(UTC)
    ) -> None:
        self._lists = lists
        self._clock = clock

    async def current(
        self, session: AsyncSession, user_id: UUID, fact_ids: Collection[UUID], *, lock: bool
    ) -> list[MemoryFactRecord]:
        """The named facts the person may forget now, oldest first."""
        statement = (
            select(FACT)
            .where(
                FACT.id.in_(tuple(fact_ids)),
                visible(user_id, await self._lists.spaces(session, user_id)),
                FACT.status == FactStatus.ACTIVE.value,
            )
            .order_by(FACT.created_at, FACT.id)
        )
        return list(await session.scalars(statement.with_for_update() if lock else statement))

    async def forget(
        self, session: AsyncSession, user_id: UUID, fact_ids: Collection[UUID]
    ) -> tuple[list[UUID], datetime]:
        """End the named facts still current; what ended and until when it can come back."""
        now = self._clock()
        ended: list[UUID] = []
        for row in await self.current(session, user_id, fact_ids, lock=True):
            write_back(row, forget(fact_of(row), EndReason.FORGOT, now), now)
            ended.append(row.id)
        return ended, now + RESTORE_WINDOW
