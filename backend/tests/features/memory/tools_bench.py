"""Leo's `memory` toolset over the slot's homes: the embedding model, the consents, the
workspaces and the meetings as doubles (memory step 6)."""

import uuid
from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest_asyncio
from prometheus_client import CollectorRegistry
from redis.asyncio import Redis
from sqlalchemy import insert, select

from shosai.core.agent_tools.context import ToolContext
from shosai.core.agent_tools.events import ActionItemExecuted
from shosai.core.events.catalog import EventTypes
from shosai.core.events.outbox import EventOutbox
from shosai.core.idempotency.action_items import ActionItems
from shosai.core.idempotency.ledger import EffectLedger
from shosai.core.idempotency.metrics import EffectKeyMetrics
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import CONSENT_READER
from shosai.features.memory.application.fact_forgets import FactForgets
from shosai.features.memory.application.fact_list import FactLists
from shosai.features.memory.application.fact_search import FactSearch
from shosai.features.memory.channels.agent_tool_handlers import MemoryTools
from shosai.features.memory.infrastructure.embeddings import Embedder
from shosai.features.memory.infrastructure.records import MemoryFactRecord
from shosai.features.notes.contracts import MEETING_READER
from shosai.features.workspaces.contracts import MEMBERSHIP_READER
from tests.features.memory.facts_api_bench import START, Meetings, Spaces
from tests.features.memory.recall_bench import MODEL, ROUTE, Consents, VectorModel, axis
from tests.harness.database_access import DatabaseAccess

OUTBOX = EventOutbox(EventTypes([ActionItemExecuted]))


@dataclass(frozen=True, slots=True)
class ToolsBench:
    """The toolset's handlers and the doubles behind them."""

    homes: DatabaseAccess
    valkey: Redis
    model: VectorModel
    consents: Consents
    spaces: Spaces
    meetings: Meetings
    tools: MemoryTools

    async def add(self, person: uuid.UUID, rows: Sequence[Mapping[str, object]]) -> list[uuid.UUID]:
        """Facts of the person in the Russian home, a minute apart, near the first axis."""
        ids = [uuid.uuid4() for _ in rows]
        values = [
            {
                "id": fact_id, "user_id": person, "kind": "fact", "source_kind": "user_statement",
                "status": "active", "confirmed": True, "embedding": axis(1),
                "embedding_model": MODEL, "created_at": START + timedelta(minutes=index),
                "last_confirmed_at": START + timedelta(minutes=index),
            } | dict(row)
            for index, (fact_id, row) in enumerate(zip(ids, rows, strict=True))
        ]  # fmt: skip
        async with self.homes.transactions.begin(TenancyScope(Home.RU, person)) as session:
            await session.execute(insert(MemoryFactRecord), values)
        return ids

    async def statuses(self, person: uuid.UUID) -> dict[str, str]:
        """Each of the person's facts' status by its statement."""
        scope = TenancyScope(Home.RU, person)
        async with self.homes.transactions.begin(scope, read_only=True) as session:
            rows = await session.scalars(
                select(MemoryFactRecord).where(MemoryFactRecord.user_id == person)
            )
            return {row.statement: row.status for row in rows}

    @staticmethod
    def context(person: uuid.UUID) -> ToolContext:
        """A call of the person's run."""
        return ToolContext(
            TenancyScope(Home.RU, person), uuid.uuid4(), datetime.now(UTC) + timedelta(seconds=30)
        )


@pytest_asyncio.fixture
async def tools_bench(homes: DatabaseAccess, valkey: Redis) -> AsyncIterator[ToolsBench]:
    model, consents, spaces, meetings = VectorModel(), Consents(), Spaces(), Meetings()
    ports = PortDirectory()
    ports.install(
        [
            CONSENT_READER.bind(consents),
            MEMBERSHIP_READER.bind(spaces),
            MEETING_READER.bind(meetings),
        ]
    )
    lists = FactLists(homes.transactions, ports)
    search = FactSearch(homes.transactions, (lists, Embedder(model, ROUTE), valkey, ports))
    items = ActionItems(EffectLedger(EffectKeyMetrics(CollectorRegistry())), OUTBOX)
    tools = MemoryTools(homes.transactions, (search, FactForgets(lists), items))
    yield ToolsBench(homes, valkey, model, consents, spaces, meetings, tools)
