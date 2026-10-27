"""Undo for a day: a forgotten or replaced fact comes back (memory step 7, ADR 0071 MM-D3).

The person's own fact, in Personal or a workspace they are in now, within 24 hours of being
forgotten or replaced: a forgotten fact is current again — a turned-down candidate waits again
— and a replaced one takes its place back as its successor ends. A fact that is already back
answers as it is, so a repeat changes nothing. Anything else — another person's, a left
workspace's, an expired one, one forgotten with everything, past the day — is
`memory_fact_not_found`.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.features.identity.contracts import Principal
from shosai.features.memory.application.fact_changes import not_found
from shosai.features.memory.application.fact_list import FactLists, FactView, view_of
from shosai.features.memory.application.fact_rows import FACT, fact_of, write_back
from shosai.features.memory.domain.facts import MemoryRuleError, restore
from shosai.features.memory.infrastructure.presence import TTL_SECONDS, has_memories_key
from shosai.features.memory.infrastructure.records import MemoryFactRecord


class FactRestore:
    """Brings the person's facts back within a day."""

    def __init__(
        self,
        transactions: HomeTransactions,
        collaborators: tuple[FactLists, Redis],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._lists, self._valkey = collaborators
        self._clock = clock

    async def restore(self, principal: Principal, fact_id: UUID) -> FactView:
        """The fact back, or as it is when it already is."""
        user_id = principal.user_id
        async with self._transactions.begin(principal.scope()) as session:
            row = await self._own(session, user_id, fact_id)
            fact = fact_of(row)
            if not (fact.current or fact.pending):
                successor = (
                    await self._find(session, user_id, row.superseded_by)
                    if row.superseded_by is not None
                    else None
                )
                try:
                    back, ended = restore(
                        fact, fact_of(successor) if successor else None, self._clock()
                    )
                except MemoryRuleError:
                    raise not_found() from None
                now = self._clock()
                write_back(row, back, now)
                if successor is not None and ended is not None:
                    write_back(successor, ended, now)
            titles = await self._lists.titles(session, user_id, [row])
            view = view_of(row, titles.get)
        await self._valkey.set(has_memories_key(user_id), "1", ex=TTL_SECONDS)
        return view

    async def _own(self, session: AsyncSession, user_id: UUID, fact_id: UUID) -> MemoryFactRecord:
        """The person's fact in a space they are in now, locked; not found otherwise."""
        row = await self._find(session, user_id, fact_id)
        if row is None:
            raise not_found()
        return row

    async def _find(
        self, session: AsyncSession, user_id: UUID, fact_id: UUID
    ) -> MemoryFactRecord | None:
        spaces = await self._lists.spaces(session, user_id)
        return await session.scalar(
            select(FACT)
            .where(FACT.id == fact_id, FACT.user_id == user_id, FACT.erase_after.is_(None))
            .where(or_(FACT.org_id.is_(None), FACT.org_id.in_(tuple(spaces))))
            .with_for_update()
        )
