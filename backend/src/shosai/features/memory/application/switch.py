"""The memory switch, and its mirror in the native `/v1/auth/me` (memory step 3).

Memory is on until the person turns it off. Off stops recall, the profile core's facts, the
toolset and every writer at once, and keeps the facts; the moment it changed is kept, so the
invariant monitor can find a fact written after it (§16.4). The desktop clients read the
switch as the draft's `memory_enabled`.
"""

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.features.identity.contracts import Principal
from shosai.features.memory.infrastructure.records import MemorySettingsRecord


async def memory_on(session: AsyncSession, user_id: UUID) -> bool:
    """Whether the person's memory is on, read in the caller's transaction."""
    enabled = await session.scalar(
        select(MemorySettingsRecord.enabled).where(MemorySettingsRecord.user_id == user_id)
    )
    return enabled is None or enabled


class MemorySwitch:
    """Reads and turns the person's memory switch."""

    def __init__(
        self,
        transactions: HomeTransactions,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._clock = clock

    async def read(self, principal: Principal) -> bool:
        """Whether memory is on for the person."""
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            return await memory_on(session, principal.user_id)

    async def turn(self, principal: Principal, *, enabled: bool) -> bool:
        """Turn memory on or off; turning it to where it is keeps its moment."""
        now = self._clock()
        async with self._transactions.begin(principal.scope()) as session:
            await session.execute(
                insert(MemorySettingsRecord)
                .values(user_id=principal.user_id, enabled=enabled, changed_at=now)
                .on_conflict_do_update(
                    index_elements=[MemorySettingsRecord.user_id],
                    set_={"enabled": enabled, "changed_at": now},
                    where=MemorySettingsRecord.enabled.is_distinct_from(enabled),
                )
            )
        return enabled

    async def native_me(self, principal: Principal) -> Mapping[str, object]:
        """The draft's `memory_enabled` of `/v1/auth/me`."""
        return {"memory_enabled": await self.read(principal)}
