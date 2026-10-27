"""What Leo remembers, read for its `memory.recall` tool (memory step 6).

With words, the person's current facts nearest to them: the words are embedded once with the
facts' model and the exact nearest are read through the b-tree on the person, above the
recall floor, the closest first. Without words, the pinned facts and then the most recently
confirmed. Only current facts in Personal and the workspaces the person is in now; nothing
while memory is off. A Russian-home person's words reach the embedding model only with their
cross-border consent, and a person known to hold nothing spares the call.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from typing import Final
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.ai.errors import AiCallError
from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import CONSENT_READER
from shosai.features.memory.application.fact_list import FactLists
from shosai.features.memory.application.fact_rows import FACT, fact_of, visible
from shosai.features.memory.application.recall import EMPTY
from shosai.features.memory.application.switch import memory_on
from shosai.features.memory.domain.facts import Fact, FactStatus
from shosai.features.memory.domain.packing import RECALL_FLOOR
from shosai.features.memory.infrastructure.embeddings import Embedder, Payer
from shosai.features.memory.infrastructure.presence import has_memories_key
from shosai.features.memory.infrastructure.records import MemoryFactRecord

FOUND_MAX: Final = 20


class SearchOutcome(StrEnum):
    """How a search ended."""

    FOUND = "found"
    OFF = "off"
    NO_CONSENT = "no_consent"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class FoundFact:
    """A current fact, the workspace it belongs to, and the meeting it came from as the person
    may read it now."""

    fact: Fact
    org_id: UUID | None
    meeting_id: UUID | None
    meeting: str | None


@dataclass(frozen=True, slots=True)
class Found:
    """The facts a search found, and how it ended."""

    outcome: SearchOutcome
    facts: tuple[FoundFact, ...] = ()


def _meeting_of(row: MemoryFactRecord) -> UUID | None:
    value = row.source_ref.get("meeting_id")
    return UUID(value) if value else None


class FactSearch:
    """Reads the person's current facts by words, or the ones that matter most."""

    def __init__(
        self,
        transactions: HomeTransactions,
        collaborators: tuple[FactLists, Embedder, Redis, PortDirectory],
    ) -> None:
        self._transactions = transactions
        self._lists, self._embedder, self._valkey, self._ports = collaborators

    async def search(self, scope: TenancyScope, words: str | None, deadline: timedelta) -> Found:
        """The facts nearest to the words, or without words the pinned and the latest."""
        user_id = scope.user_id
        if user_id is None:
            return Found(SearchOutcome.OFF)
        if words is None:
            return await self._read(scope, user_id, None)
        refused, consent = await self._refusal(scope, user_id)
        if refused is not None:
            return Found(refused)
        if await self._valkey.get(has_memories_key(user_id)) == EMPTY:
            return Found(SearchOutcome.FOUND)
        try:
            vector = await self._embedder.question(
                Payer(scope, consent), words, f"tool:{user_id}", deadline
            )
        except AiCallError:
            return Found(SearchOutcome.FAILED)
        return await self._read(scope, user_id, vector)

    async def _refusal(
        self, scope: TenancyScope, user_id: UUID
    ) -> tuple[SearchOutcome | None, bool]:
        """Why the words may not be embedded, if they may not, and the person's consent."""
        async with self._transactions.begin(scope, read_only=True) as session:
            if not await memory_on(session, user_id):
                return SearchOutcome.OFF, False
            consent = scope.home is not Home.RU or await self._ports.get(
                CONSENT_READER
            ).cross_border(session, user_id)
        return (None if consent else SearchOutcome.NO_CONSENT), consent

    async def _read(
        self, scope: TenancyScope, user_id: UUID, vector: Sequence[float] | None
    ) -> Found:
        async with self._transactions.begin(scope, read_only=True) as session:
            if not await memory_on(session, user_id):
                return Found(SearchOutcome.OFF)
            seen = visible(user_id, await self._lists.spaces(session, user_id))
            current = select(FACT).where(seen, FACT.status == FactStatus.ACTIVE.value)
            rows = await self._rows(session, current, vector)
            titles = await self._lists.titles(session, user_id, rows)
        found = tuple(
            FoundFact(fact_of(row), row.org_id, meeting, titles.get(meeting) if meeting else None)
            for row in rows
            for meeting in (_meeting_of(row),)
        )
        return Found(SearchOutcome.FOUND, found)

    async def _rows(
        self,
        session: AsyncSession,
        current: Select[MemoryFactRecord],
        vector: Sequence[float] | None,
    ) -> list[MemoryFactRecord]:
        """The latest without a vector; with one, the nearest above the floor."""
        if vector is None:
            latest = current.order_by(FACT.pinned.desc(), FACT.last_confirmed_at.desc(), FACT.id)
            return list(await session.scalars(latest.limit(FOUND_MAX)))
        distance = FACT.embedding.cosine_distance(vector)
        nearest = (
            current.add_columns(distance)
            .where(FACT.embedding_model == self._embedder.model)
            .order_by(distance)
            .limit(FOUND_MAX)
        )
        return [
            row for row, gap in (await session.execute(nearest)).all() if 1 - gap >= RECALL_FLOOR
        ]
