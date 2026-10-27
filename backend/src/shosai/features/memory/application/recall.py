"""What Leo recalls of the person for a turn, and the profile core (Leo §7.2, §7.3, step 4).

Recall embeds the question with the start of the previous answer once, then reads the
person's current facts of the current model in Personal and the workspaces they are in now —
the exact nearest 40, through the b-tree on the person (MM-D6) — and keeps what is above the
floor, packed within the turn's budget. It never fails a turn: no consent, memory off, nothing
held, a late or failed call each answer nothing and are counted. The "has memories" bit spares
an embedding call for a person with no current fact. The profile core is read in the agent's
own transaction: whether memory is on, then pinned facts and preferences in a fixed order.
"""

import asyncio
import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Final
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.ai.errors import AiCallError
from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.ids import new_id
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.agent.contracts.memory import ProfileCore, RecalledFact, RecallRequest
from shosai.features.memory.application.fact_list import FactLists
from shosai.features.memory.application.fact_rows import FACT, fact_of, visible
from shosai.features.memory.application.switch import memory_on
from shosai.features.memory.domain.facts import Fact, FactKind, FactStatus
from shosai.features.memory.domain.packing import RECALL_FLOOR, RECALL_POOL, Near, profile, recalled
from shosai.features.memory.domain.trust import label_of, taint_of
from shosai.features.memory.infrastructure.embeddings import Embedder, Payer
from shosai.features.memory.infrastructure.metrics import MemoryMetrics, RecallOutcome
from shosai.features.memory.infrastructure.presence import TTL_SECONDS, has_memories_key

EMPTY: Final = b"0"
# Столько закреплённых фактов и предпочтений профиль читает, прежде чем уложить их в бюджет.
PROFILE_ROWS: Final = 200


def recalled_fact(fact: Fact) -> RecalledFact:
    """The agent's view of a fact: its words, kind, label and the taint it brings."""
    return RecalledFact(fact.statement, fact.kind.value, label_of(fact.source), taint_of(fact))


class Recall:
    """The `agent.memory_recall` and `agent.profile_facts` bindings."""

    def __init__(
        self,
        transactions: HomeTransactions,
        collaborators: tuple[FactLists, Embedder, Redis, MemoryMetrics],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._lists, self._embedder, self._valkey, self._metrics = collaborators
        self._clock = clock

    async def recall(self, request: RecallRequest) -> tuple[RecalledFact, ...]:
        """The facts that matter for the question; nothing, counted, when there are none."""
        started = time.monotonic()
        try:
            async with asyncio.timeout(request.deadline.total_seconds()):
                outcome, facts = await self._recall(request)
        except TimeoutError:
            outcome, facts = RecallOutcome.LATE, ()
        self._metrics.recalled(outcome, time.monotonic() - started, len(facts))
        return facts

    async def _recall(
        self, request: RecallRequest
    ) -> tuple[RecallOutcome, tuple[RecalledFact, ...]]:
        if request.home is Home.RU and not request.cross_border_consent:
            return RecallOutcome.NO_CONSENT, ()
        if await self._valkey.get(has_memories_key(request.user_id)) == EMPTY:
            return RecallOutcome.EMPTY, ()
        payer = Payer(TenancyScope(request.home, request.user_id), request.cross_border_consent)
        try:
            vector = await self._embedder.question(
                payer, request.query, str(new_id()), request.deadline
            )
        except AiCallError:
            return RecallOutcome.FAILED, ()
        near, enabled, held = await self._nearest(request.home, request.user_id, vector)
        if not enabled:
            return RecallOutcome.OFF, ()
        if not held:
            await self._valkey.set(has_memories_key(request.user_id), EMPTY, ex=TTL_SECONDS)
            return RecallOutcome.EMPTY, ()
        facts = recalled(near, self._clock(), RECALL_FLOOR, request.max_tokens)
        outcome = RecallOutcome.HIT if facts else RecallOutcome.EMPTY
        return outcome, tuple(recalled_fact(fact) for fact in facts)

    async def _nearest(
        self, home: Home, user_id: UUID, vector: Sequence[float]
    ) -> tuple[list[Near], bool, bool]:
        """The nearest current facts, whether memory is on, and whether any fact is held."""
        async with self._transactions.begin(TenancyScope(home, user_id), read_only=True) as s:
            if not await memory_on(s, user_id):
                return [], False, True
            spaces = await self._lists.spaces(s, user_id)
            distance = FACT.embedding.cosine_distance(vector)
            rows = (
                await s.execute(
                    select(FACT, distance)
                    .where(
                        visible(user_id, spaces),
                        FACT.status == FactStatus.ACTIVE.value,
                        FACT.embedding_model == self._embedder.model,
                    )
                    .order_by(distance)
                    .limit(RECALL_POOL)
                )
            ).all()
            held = bool(rows) or await self._held(s, user_id)
        return [Near(fact_of(row), 1 - float(gap)) for row, gap in rows], True, held

    @staticmethod
    async def _held(session: AsyncSession, user_id: UUID) -> bool:
        """Whether the person holds any current fact, embedded or not yet."""
        found = await session.scalar(
            select(FACT.id)
            .where(FACT.user_id == user_id, FACT.status == FactStatus.ACTIVE.value)
            .where(FACT.valid_to.is_(None))
            .limit(1)
        )
        return found is not None

    async def profile(self, session: AsyncSession, user_id: UUID, max_tokens: int) -> ProfileCore:
        """Pinned facts, then preferences, within the budget, in the agent's transaction."""
        if not await memory_on(session, user_id):
            return ProfileCore(enabled=False, facts=())
        spaces = await self._lists.spaces(session, user_id)
        rows = await session.scalars(
            select(FACT)
            .where(
                visible(user_id, spaces),
                FACT.status == FactStatus.ACTIVE.value,
                or_(FACT.pinned, FACT.kind == FactKind.PREFERENCE.value),
            )
            .order_by(FACT.pinned.desc(), FACT.last_confirmed_at.desc())
            .limit(PROFILE_ROWS)
        )
        chosen = profile([fact_of(row) for row in rows], self._clock(), max_tokens)
        return ProfileCore(enabled=True, facts=tuple(recalled_fact(fact) for fact in chosen))
