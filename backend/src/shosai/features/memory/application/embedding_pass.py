"""The embedding pass: every fact gets the vector of the current model (memory step 4).

A fact is written without its vector — by an edit, an admission or a migration — and a model
change leaves old vectors behind; once a minute per home the pass finds such facts, person by
person after the last one it served, so nobody waits behind people it cannot serve, and
embeds their statements as the person, under their cross-border consent. A fact edited or
ended meanwhile keeps whatever the person did: the vector lands only on the same statement,
still waiting for one. Until then the fact is listed but not recalled.
"""

from collections import defaultdict
from collections.abc import Sequence
from typing import Final
from uuid import UUID

import structlog
from redis.asyncio import Redis
from sqlalchemy import ColumnElement, and_, or_, select, update

from shosai.core.ai.errors import AiCallError
from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import CONSENT_READER
from shosai.features.memory.application.fact_rows import FACT
from shosai.features.memory.domain.facts import FactStatus
from shosai.features.memory.infrastructure.embeddings import Embedder, Payer
from shosai.features.memory.infrastructure.metrics import EmbedOutcome, MemoryMetrics

# Столько фактов проход берёт за один тик дома: ≈ десяток вызовов поставщика.
ROWS_PER_TICK: Final = 400
CURSOR_KEY: Final = "memory:embed:after:{home}"
log = structlog.stdlib.get_logger(__name__)


def person_of(stored: bytes | str | None) -> UUID | None:
    """The person a stored cursor names, or None."""
    if not stored:
        return None
    return UUID(stored.decode() if isinstance(stored, bytes) else stored)


def waiting_for(model: str) -> ColumnElement[bool]:
    """A current or waiting fact without a vector of the model."""
    return and_(
        FACT.status.in_((FactStatus.ACTIVE.value, FactStatus.CANDIDATE.value)),
        FACT.valid_to.is_(None),
        or_(FACT.embedding.is_(None), FACT.embedding_model != model),
    )


class EmbeddingPass:
    """Gives the facts of one home the current model's vectors."""

    def __init__(
        self,
        transactions: HomeTransactions,
        collaborators: tuple[PortDirectory, Embedder, Redis, MemoryMetrics],
    ) -> None:
        self._transactions = transactions
        self._ports, self._embedder, self._valkey, self._metrics = collaborators

    async def run(self, home: Home) -> int:
        """One tick of the home: the facts found, embedded where the person allows."""
        cursor_key = CURSOR_KEY.format(home=home.value)
        after = await self._valkey.get(cursor_key)
        found = await self._waiting(home, person_of(after))
        if not found and after:
            found = await self._waiting(home, None)
        people: dict[UUID, list[tuple[UUID, str]]] = defaultdict(list)
        for user_id, fact_id, statement in found:
            people[user_id].append((fact_id, statement))
        for user_id, facts in people.items():
            await self._embed(home, user_id, facts)
        if people:
            await self._valkey.set(cursor_key, str(max(people)))
        return len(found)

    async def _waiting(self, home: Home, after: UUID | None) -> Sequence[tuple[UUID, UUID, str]]:
        """Facts waiting for a vector, people after `after` first, as the sweep role."""
        query = select(FACT.user_id, FACT.id, FACT.statement).where(
            waiting_for(self._embedder.model)
        )
        if after is not None:
            query = query.where(FACT.user_id > after)
        query = query.order_by(FACT.user_id, FACT.id).limit(ROWS_PER_TICK)
        scope = TenancyScope(home)
        async with self._transactions.begin(scope, read_only=True, sweep=True) as session:
            return [(row.user_id, row.id, row.statement) for row in await session.execute(query)]

    async def _embed(self, home: Home, user_id: UUID, facts: list[tuple[UUID, str]]) -> None:
        scope = TenancyScope(home, user_id)
        async with self._transactions.begin(scope, read_only=True) as session:
            consent = home is not Home.RU or await self._ports.get(CONSENT_READER).cross_border(
                session, user_id
            )
        if not consent:
            self._metrics.embedded(EmbedOutcome.NO_CONSENT, len(facts))
            return
        key = f"{min(fact_id for fact_id, _ in facts)}:{len(facts)}:{self._embedder.model}"
        try:
            vectors = await self._embedder.statements(
                Payer(scope, consent), [statement for _, statement in facts], key
            )
        except AiCallError as error:
            log.warning("Векторы фактов не получены", failure=error.failure.value)
            self._metrics.embedded(EmbedOutcome.FAILED, len(facts))
            return
        model = self._embedder.model
        async with self._transactions.begin(scope) as session:
            for (fact_id, statement), vector in zip(facts, vectors, strict=True):
                await session.execute(
                    update(FACT)
                    .where(FACT.id == fact_id, FACT.statement == statement, waiting_for(model))
                    .values(embedding=vector, embedding_model=model)
                )
        self._metrics.embedded(EmbedOutcome.EMBEDDED, len(facts))
