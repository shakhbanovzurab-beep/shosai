"""The summary, its box and restore over the slot's homes and over HTTP: the model, consents,
workspaces, meetings and profiles as doubles (memory step 7)."""

import json
import uuid
from collections.abc import AsyncIterator, Collection, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import timedelta

import httpx
import pytest_asyncio
from prometheus_client import CollectorRegistry
from redis.asyncio import Redis
from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.ai.calls import CallContext, ModelRoute
from shosai.core.ai.requests import ChatRequest, TextPart
from shosai.core.ai.results import ChatResult, Usage
from shosai.core.idempotency.ledger import EffectLedger
from shosai.core.idempotency.metrics import EffectKeyMetrics
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.kv.metrics import KeyValueMetrics
from shosai.core.kv.rate_limits import RateLimiter
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import (
    ACCOUNT_PROFILE_READER,
    AUTHENTICATOR,
    CONSENT_READER,
    AccountProfile,
)
from shosai.features.memory.application.box_messages import BoxMessages
from shosai.features.memory.application.fact_changes import FactChanges
from shosai.features.memory.application.fact_list import FactLists
from shosai.features.memory.application.fact_restore import FactRestore
from shosai.features.memory.application.summaries import Summaries
from shosai.features.memory.application.summary_facts import SummaryFacts
from shosai.features.memory.application.switch import MemorySwitch
from shosai.features.memory.channels.http.facts import build_memory_router
from shosai.features.memory.channels.http.summary import build_summary_router
from shosai.features.memory.infrastructure.memory_model import MemoryModel
from shosai.features.memory.infrastructure.metrics import MemoryMetrics, SummaryTrigger
from shosai.features.memory.infrastructure.records import MemoryFactRecord, MemorySummaryRecord
from shosai.features.memory.infrastructure.summary_model import SummaryModel
from shosai.features.notes.contracts import MEETING_READER
from shosai.features.workspaces.contracts import MEMBERSHIP_READER
from tests.core.web.probe_app import build_probe_app, client_of
from tests.features.billing.people_bench import BearerOfTheTest
from tests.features.memory.admission_bench import CHAT
from tests.features.memory.facts_api_bench import START, Meetings, Spaces
from tests.features.memory.recall_bench import Consents
from tests.harness.database_access import DatabaseAccess


@dataclass
class Writer:
    """The memory model: the next answer for each feature, and what it was asked."""

    answers: dict[str, list[object]] = field(default_factory=dict)
    asked: list[tuple[CallContext, str]] = field(default_factory=list)

    async def chat(
        self, context: CallContext, route: ModelRoute, request: ChatRequest
    ) -> ChatResult:
        """The feature's next answer, as JSON text."""
        read = "".join(
            part.text for part in request.messages[-1].parts if isinstance(part, TextPart)
        )
        self.asked.append((context, read))
        answer = self.answers[context.feature].pop(0)
        text = answer if isinstance(answer, str) else json.dumps(answer)
        return ChatResult(text, (), "stop", route.primary, Usage(input_tokens=1, output_tokens=1))


@dataclass
class Languages:
    """Each person's interface language."""

    of: dict[uuid.UUID, str] = field(default_factory=dict)

    async def profile(self, session: AsyncSession, user_id: uuid.UUID) -> AccountProfile | None:
        """The person's profile."""
        del session
        return AccountProfile("Anna Petrova", self.of.get(user_id, "en"), "Europe/Berlin")

    async def names(
        self, session: AsyncSession, user_ids: Collection[uuid.UUID]
    ) -> Mapping[uuid.UUID, str]:
        """Every person is Anna here."""
        del session
        return dict.fromkeys(user_ids, "Anna Petrova")


@dataclass(frozen=True, slots=True)
class SummaryBench:
    """The services, the routes and the doubles behind them."""

    homes: DatabaseAccess
    http: httpx.AsyncClient
    writer: Writer
    consents: Consents
    languages: Languages
    queued: list[tuple[TenancyScope, SummaryTrigger]]
    summaries: Summaries
    box: BoxMessages
    restore: FactRestore
    switch: MemorySwitch

    async def add(self, person: uuid.UUID, rows: Sequence[Mapping[str, object]]) -> list[uuid.UUID]:
        """Facts of the person in the Russian home, a minute apart."""
        ids = [uuid.uuid4() for _ in rows]
        values = [
            {
                "id": fact_id, "user_id": person, "kind": "fact", "source_kind": "user_statement",
                "status": "active", "confirmed": True, "created_at": START + timedelta(minutes=i),
                "last_confirmed_at": START + timedelta(minutes=i),
            } | dict(row)
            for i, (fact_id, row) in enumerate(zip(ids, rows, strict=True))
        ]  # fmt: skip
        async with self.homes.transactions.begin(TenancyScope(Home.RU, person)) as session:
            await session.execute(insert(MemoryFactRecord), values)
        return ids

    async def written_hours_ago(self, person: uuid.UUID, hours: int) -> None:
        """Move the summary's last write back in time."""
        async with self.homes.transactions.begin(TenancyScope(Home.RU, person)) as session:
            await session.execute(
                update(MemorySummaryRecord)
                .where(MemorySummaryRecord.user_id == person)
                .values(written_at=MemorySummaryRecord.written_at - timedelta(hours=hours))
            )

    async def facts(self, person: uuid.UUID) -> dict[str, tuple[str, bool]]:
        """Each of the person's facts' status and whether it is closed, by statement."""
        scope = TenancyScope(Home.RU, person)
        async with self.homes.transactions.begin(scope, read_only=True) as session:
            rows = await session.scalars(
                select(MemoryFactRecord).where(MemoryFactRecord.user_id == person)
            )
            return {row.statement: (row.status, row.valid_to is not None) for row in rows}


@pytest_asyncio.fixture
async def summary_bench(homes: DatabaseAccess, valkey: Redis) -> AsyncIterator[SummaryBench]:
    writer, consents, languages = Writer(), Consents(), Languages()
    ports = PortDirectory()
    ports.install(
        [
            AUTHENTICATOR.bind(BearerOfTheTest()),
            CONSENT_READER.bind(consents),
            MEMBERSHIP_READER.bind(Spaces()),
            MEETING_READER.bind(Meetings()),
            ACCOUNT_PROFILE_READER.bind(languages),
        ]
    )
    queued: list[tuple[TenancyScope, SummaryTrigger]] = []

    async def queue(scope: TenancyScope, trigger: SummaryTrigger) -> None:
        queued.append((scope, trigger))

    registry = CollectorRegistry()
    metrics = MemoryMetrics(registry)
    lists, effects = FactLists(homes.transactions, ports), EffectLedger(EffectKeyMetrics(registry))
    model = SummaryModel(MemoryModel(writer, CHAT))
    facts = SummaryFacts(lists)
    summaries = Summaries(homes.transactions, (facts, model, ports, metrics), (queue, valkey))
    limiter = RateLimiter(valkey, KeyValueMetrics(registry))
    box = BoxMessages(
        homes.transactions, (lists, facts, model, summaries), (effects, limiter, valkey, ports)
    )
    restore = FactRestore(homes.transactions, (lists, valkey))
    switch = MemorySwitch(homes.transactions)
    routers = (
        build_summary_router((summaries, box), ports, limiter),
        build_memory_router(
            (
                lists,
                FactChanges(homes.transactions, (lists, effects, valkey, metrics)),
                switch,
                restore,
            ),
            ports,
        ),
    )
    async with client_of(build_probe_app(extra=routers).app) as http:
        yield SummaryBench(
            homes, http, writer, consents, languages, queued, summaries, box, restore, switch
        )
