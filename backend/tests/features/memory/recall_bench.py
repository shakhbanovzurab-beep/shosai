"""Recall, the profile core and the embedding pass over the slot's homes, with a provider double
that gives each statement a fixed vector (memory step 4)."""

import asyncio
import math
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import timedelta

import pytest_asyncio
from prometheus_client import CollectorRegistry
from redis.asyncio import Redis
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.ai.calls import CallContext, ModelRef, ModelRoute, Provider
from shosai.core.ai.errors import AiCallError, AiFailure
from shosai.core.ai.requests import EmbeddingRequest
from shosai.core.ai.results import Embeddings, Usage
from shosai.core.config.roles import ProcessRole
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.agent.contracts.memory import RecallRequest
from shosai.features.identity.contracts import CONSENT_READER
from shosai.features.memory.application.embedding_pass import EmbeddingPass
from shosai.features.memory.application.fact_list import FactLists
from shosai.features.memory.application.recall import Recall
from shosai.features.memory.infrastructure.embeddings import DOCUMENT_PREFIX, QUERY_PREFIX, Embedder
from shosai.features.memory.infrastructure.metrics import MemoryMetrics
from shosai.features.memory.infrastructure.records import EMBEDDING_DIMENSIONS, MemoryFactRecord
from shosai.features.workspaces.contracts import MEMBERSHIP_READER
from tests.features.memory.facts_api_bench import Spaces
from tests.harness.database_access import (
    DatabaseAccess,
    ProcessShape,
    open_database_access,
    slot_urls,
)
from tests.harness.run_slot import RunSlot

MODEL = "google/gemini-embedding-2"
ROUTE = ModelRoute(ModelRef(Provider.OPENROUTER, MODEL))


def axis(*weights: float) -> list[float]:
    """A unit vector with the given leading components."""
    vector = [*weights, *([0.0] * (EMBEDDING_DIMENSIONS - len(weights)))]
    norm = math.sqrt(sum(value * value for value in vector))
    return [value / norm for value in vector]


@dataclass
class VectorModel:
    """The provider's embedding call: a vector per text it knows, a failure or a delay."""

    known: dict[str, list[float]] = field(default_factory=dict)
    delay: timedelta = timedelta(0)
    failure: AiFailure | None = None
    calls: list[tuple[CallContext, tuple[str, ...], bool]] = field(default_factory=list)
    # Что случается до ответа: например, человек правит факт, пока вектор считается.
    meanwhile: Callable[[], Awaitable[None]] | None = None

    async def embed(
        self,
        context: CallContext,
        route: ModelRoute,
        request: EmbeddingRequest,
        *,
        cost_later: bool = False,
    ) -> Embeddings:
        """Vectors of the texts, with their prefixes taken off."""
        self.calls.append((context, request.texts, cost_later))
        if self.meanwhile is not None:
            await self.meanwhile()
        await asyncio.sleep(self.delay.total_seconds())
        if self.failure is not None:
            raise AiCallError(self.failure)
        texts = [
            text.removeprefix(QUERY_PREFIX).removeprefix(DOCUMENT_PREFIX) for text in request.texts
        ]
        vectors = tuple(tuple(self.known.get(text, axis(0, 0, 1))) for text in texts)
        return Embeddings(vectors, route.primary, Usage(input_tokens=len(texts)))


@dataclass
class Consents:
    """Who consents to cross-border transfer."""

    given: set[uuid.UUID] = field(default_factory=set)

    async def cross_border(self, session: AsyncSession, user_id: uuid.UUID) -> bool:
        """Whether the person consents."""
        del session
        return user_id in self.given

    async def improve_models(self, session: AsyncSession, user_id: uuid.UUID) -> bool:
        """Never asked by memory."""
        del session, user_id
        return False


@dataclass(frozen=True, slots=True)
class RecallBench:
    """Recall and the pass over the slot, the doubles behind them."""

    homes: DatabaseAccess
    valkey: Redis
    model: VectorModel
    consents: Consents
    spaces: Spaces
    recall: Recall
    embedding: EmbeddingPass

    async def add(self, person: uuid.UUID, rows: Sequence[Mapping[str, object]]) -> list[uuid.UUID]:
        """Facts of the person in the Russian home."""
        ids = [uuid.uuid4() for _ in rows]
        values = [
            {"id": fact_id, "user_id": person, "kind": "fact", "source_kind": "user_statement",
             "status": "active", "confirmed": True} | dict(row)
            for fact_id, row in zip(ids, rows, strict=True)
        ]  # fmt: skip
        async with self.homes.transactions.begin(TenancyScope(Home.RU, person)) as session:
            await session.execute(insert(MemoryFactRecord), values)
        return ids

    def ask(self, person: uuid.UUID, query: str, *, consent: bool = True) -> RecallRequest:
        """A turn's request to recall."""
        return RecallRequest(
            home=Home.RU, user_id=person, query=query, cross_border_consent=consent,
            max_tokens=600, deadline=timedelta(milliseconds=350),
        )  # fmt: skip


@pytest_asyncio.fixture
async def recall_bench(
    homes: DatabaseAccess, valkey: Redis, run_slot: RunSlot
) -> AsyncIterator[RecallBench]:
    model, consents, spaces = VectorModel(), Consents(), Spaces()
    ports = PortDirectory()
    ports.install([CONSENT_READER.bind(consents), MEMBERSHIP_READER.bind(spaces)])
    lists = FactLists(homes.transactions, ports)
    embedder = Embedder(model, ROUTE)
    metrics = MemoryMetrics(CollectorRegistry())
    recall = Recall(homes.transactions, (lists, embedder, valkey, metrics))
    shape = ProcessShape(role=ProcessRole.WORKERS)
    # Проход эмбеддингов обходит дом ролью обхода: она открыта только воркерам.
    async with open_database_access(slot_urls(run_slot), shape) as workers:
        await workers.gate.verify_at_start()
        embedding = EmbeddingPass(workers.transactions, (ports, embedder, valkey, metrics))
        yield RecallBench(homes, valkey, model, consents, spaces, recall, embedding)
