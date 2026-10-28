"""Memory's upkeep, departures and invariant over the slot's homes, through the sweep role of a
workers process: the workspaces, meetings and summary queue as doubles (memory step 8)."""

import uuid
from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest_asyncio
from prometheus_client import CollectorRegistry
from redis.asyncio import Redis
from sqlalchemy import insert, select

from shosai.core.config.roles import ProcessRole
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import ACCOUNT_PROFILE_READER, CONSENT_READER
from shosai.features.memory.application.departures import Departures
from shosai.features.memory.application.fact_list import FactLists
from shosai.features.memory.application.forgetting import Forgetting
from shosai.features.memory.application.invariants import MemoryInvariants
from shosai.features.memory.application.summaries import Summaries
from shosai.features.memory.application.summary_facts import SummaryFacts
from shosai.features.memory.application.upkeep import Upkeep
from shosai.features.memory.infrastructure.memory_model import MemoryModel
from shosai.features.memory.infrastructure.metrics import MemoryMetrics, SummaryTrigger
from shosai.features.memory.infrastructure.records import MemoryFactRecord, MemoryRefusalRecord
from shosai.features.memory.infrastructure.summary_model import SummaryModel
from shosai.features.notes.contracts import MEETING_READER
from shosai.features.workspaces.contracts import MEMBERSHIP_READER
from tests.features.memory.admission_bench import CHAT
from tests.features.memory.facts_api_bench import Meetings, Spaces
from tests.features.memory.recall_bench import MODEL, Consents, axis
from tests.features.memory.summary_bench import Languages, Writer
from tests.harness.database_access import (
    DatabaseAccess,
    ProcessShape,
    open_database_access,
    slot_urls,
)
from tests.harness.run_slot import RunSlot

NOW = datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class UpkeepBench:
    """The upkeep's services, the doubles behind them and the slot's homes."""

    homes: DatabaseAccess
    valkey: Redis
    spaces: Spaces
    meetings: Meetings
    queued: list[tuple[TenancyScope, SummaryTrigger]]
    upkeep: Upkeep
    departures: Departures
    invariants: MemoryInvariants
    registry: CollectorRegistry
    forgetting: Forgetting

    async def add(self, person: uuid.UUID, rows: Sequence[Mapping[str, object]]) -> list[uuid.UUID]:
        """Facts of the person in the Russian home, confirmed now unless the row says else."""
        ids = [uuid.uuid4() for _ in rows]
        values = [
            {"id": fact_id, "user_id": person, "kind": "fact", "source_kind": "user_statement",
             "status": "active", "confirmed": True, "created_at": NOW, "last_confirmed_at": NOW,
             "statement": f"Fact {index}"} | dict(row)
            for index, (fact_id, row) in enumerate(zip(ids, rows, strict=True))
        ]  # fmt: skip
        async with self.homes.transactions.begin(TenancyScope(Home.RU, person)) as session:
            await session.execute(insert(MemoryFactRecord), values)
        return ids

    async def trace(self, person: uuid.UUID, refused_at: datetime) -> uuid.UUID:
        """A trace of a refusal of the person, at the moment given."""
        trace_id = uuid.uuid4()
        async with self.homes.transactions.begin(TenancyScope(Home.RU, person)) as session:
            await session.execute(
                insert(MemoryRefusalRecord),
                [{"id": trace_id, "user_id": person, "embedding": axis(1),
                  "embedding_model": MODEL, "refused_at": refused_at}],
            )  # fmt: skip
        return trace_id

    async def traces(self, person: uuid.UUID) -> set[uuid.UUID]:
        """The ids of the person's traces."""
        scope = TenancyScope(Home.RU, person)
        async with self.homes.transactions.begin(scope, read_only=True) as session:
            return set(await session.scalars(select(MemoryRefusalRecord.id)))

    async def rows(self, person: uuid.UUID) -> dict[str, MemoryFactRecord]:
        """The person's rows by statement."""
        scope = TenancyScope(Home.RU, person)
        async with self.homes.transactions.begin(scope, read_only=True) as session:
            found = await session.scalars(
                select(MemoryFactRecord).where(MemoryFactRecord.user_id == person)
            )
            return {row.statement: row for row in found}


@pytest_asyncio.fixture
async def upkeep_bench(
    homes: DatabaseAccess, valkey: Redis, run_slot: RunSlot
) -> AsyncIterator[UpkeepBench]:
    spaces, meetings = Spaces(), Meetings()
    ports = PortDirectory()
    ports.install(
        [
            CONSENT_READER.bind(Consents()),
            MEMBERSHIP_READER.bind(spaces),
            MEETING_READER.bind(meetings),
            ACCOUNT_PROFILE_READER.bind(Languages()),
        ]
    )
    queued: list[tuple[TenancyScope, SummaryTrigger]] = []

    async def queue(scope: TenancyScope, trigger: SummaryTrigger) -> None:
        queued.append((scope, trigger))

    registry = CollectorRegistry()
    metrics = MemoryMetrics(registry)
    shape = ProcessShape(role=ProcessRole.WORKERS)
    # Обходы читают дом ролью обхода: она открыта только воркерам.
    async with open_database_access(slot_urls(run_slot), shape) as workers:
        await workers.gate.verify_at_start()
        transactions = workers.transactions
        lists = FactLists(transactions, ports)
        summaries = Summaries(
            transactions,
            (SummaryFacts(lists), SummaryModel(MemoryModel(Writer(), CHAT)), ports, metrics),
            (queue, valkey),
        )
        yield UpkeepBench(
            homes, valkey, spaces, meetings, queued,
            Upkeep(transactions, (summaries, valkey, metrics)),
            Departures(transactions, (ports, metrics)),
            MemoryInvariants(transactions, metrics), registry, Forgetting(transactions, metrics),
        )  # fmt: skip
