"""Turns end to end over the slot's homes and Valkey (agent step 5a).

The API's routes admit and stream; the `agent` queue is an inline worker that drives a sent
turn at once in the background, unless the bench holds it to play a lost worker; the model is
a script of pieces, with a pause or a gate between them and an optional failure at the end.
The plan's token decision and the person's consent are doubles the test sets.
"""

import asyncio
import json
import uuid
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Final

import httpx
import pytest_asyncio
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from prometheus_client import CollectorRegistry
from redis.asyncio import Redis

from shosai.core.agent_tools.catalog import AgentToolCatalog
from shosai.core.ai.calls import ModelRef, ModelRoute, Provider
from shosai.core.config.roles import ProcessRole
from shosai.core.db.transactions import HomeTransactions
from shosai.core.documents.extraction import DocumentReader
from shosai.core.events.catalog import EventTypes
from shosai.core.events.outbox import EventOutbox
from shosai.core.idempotency.ledger import EffectLedger
from shosai.core.idempotency.metrics import EffectKeyMetrics
from shosai.core.kernel.homes import Home
from shosai.core.kv.metrics import KeyValueMetrics
from shosai.core.kv.rate_limits import RateLimit, RateLimiter
from shosai.core.ports.directory import PortDirectory
from shosai.features.agent.application.action_cards import ActionCards
from shosai.features.agent.application.action_proposal import ActionProposer
from shosai.features.agent.application.friction_judging import FrictionJudging
from shosai.features.agent.application.history import History
from shosai.features.agent.application.model_stream import Pace
from shosai.features.agent.application.result_pages import ResultPages
from shosai.features.agent.application.run_attachments import AttachmentReader
from shosai.features.agent.application.run_context import ContextBuilder
from shosai.features.agent.application.run_engine import RunEngine
from shosai.features.agent.application.run_engine_parts import EngineParts
from shosai.features.agent.application.run_registry import RunRegistry
from shosai.features.agent.application.run_sources import RunSources
from shosai.features.agent.application.run_streams import RunStreams
from shosai.features.agent.application.run_telemetry import RunTelemetry
from shosai.features.agent.application.threads import Threads
from shosai.features.agent.application.tool_offer import TurnRouting
from shosai.features.agent.application.tool_registry import ToolRegistry
from shosai.features.agent.application.tool_round import ToolParts
from shosai.features.agent.application.turn_commit import TurnParts
from shosai.features.agent.application.turn_start import TurnStarter
from shosai.features.agent.channels.agent_tools import core_tools
from shosai.features.agent.channels.http.callers import operator_mount, person_mount
from shosai.features.agent.channels.http.threads import build_threads_router
from shosai.features.agent.channels.http.turns import build_turns_router
from shosai.features.agent.contracts import FRICTION_JUDGE, INJECTION_JUDGE, TURN_ROUTER
from shosai.features.agent.contracts.effort import TURN_EFFORT_JUDGE
from shosai.features.agent.infrastructure.fleet import Fleet
from shosai.features.agent.infrastructure.log_tail import LogTail
from shosai.features.agent.infrastructure.run_log import RunLog
from shosai.features.agent.infrastructure.run_metrics import RunMetrics
from shosai.features.agent.infrastructure.thread_lease import ThreadLeases
from shosai.features.agent.infrastructure.tool_metrics import ToolMetrics
from shosai.features.agent.infrastructure.turn_graph import turn_graph
from shosai.features.agent.infrastructure.turn_saver import TurnSaver
from shosai.features.agent.module import AGENT
from shosai.features.billing.contracts import TOKEN_ALLOWANCE
from shosai.features.files.application.upload_rules import UploadRequest
from shosai.features.files.contracts import UPLOADS, UploadPurpose
from shosai.features.identity.contracts import (
    ACCOUNT_PROFILE_READER,
    ADMIN_GATE,
    AUTHENTICATOR,
    CONSENT_READER,
    Principal,
)
from shosai.features.notes.contracts import MEETING_READER
from shosai.features.workspaces.contracts import MEMBERSHIP_READER, WORKSPACE_READER
from shosai.features.workspaces.infrastructure.membership_reader import (
    MembershipDirectory,
    WorkspaceDirectory,
)
from tests.core.web.probe_app import build_probe_app, client_of
from tests.features.agent.bench_doubles import BenchDoubles, memory_bindings
from tests.features.agent.tool_doubles import ProbeTools
from tests.features.agent.turn_doubles import (
    WAIT,
    AdminSession,
    InlineQueue,
    Meetings,
    Profiles,
    ScriptedModel,
    Terms,
)
from tests.features.billing.people_bench import BearerOfTheTest, bearer
from tests.features.files.upload_bench import UploadBench
from tests.harness.connections import Connection
from tests.harness.database_access import (
    DatabaseAccess,
    ProcessShape,
    open_database_access,
    slot_urls,
)
from tests.harness.run_slot import RunSlot

HOME: Final = Home.EU
ROUTE: Final = ModelRoute(ModelRef(Provider.OPENROUTER, "probe/leo"))
QUICK: Final = Pace(flush=timedelta(milliseconds=20), stall=timedelta(seconds=2))
# Тесты задают много ходов подряд; предел частоты проверяет свой тест.
GENEROUS: Final = RateLimit("agent.turn_bench", 1_000, timedelta(minutes=1), 1_000)


@dataclass(frozen=True, slots=True)
class TurnBench:
    """The routes, the inline worker, the model and the terms over the slot."""

    http: httpx.AsyncClient
    homes: DatabaseAccess
    valkey: Redis
    model: ScriptedModel
    queue: InlineQueue
    terms: Terms
    parts: EngineParts
    run_slot: RunSlot
    meetings: Meetings
    # Реестр метрик стенда и снятые спаны: тесты телеметрии читают их.
    observed: tuple[CollectorRegistry, InMemorySpanExporter]
    tools: ProbeTools
    catalog: AgentToolCatalog
    # Порты стенда: карточки читают через них профиль и пространства.
    ports: PortDirectory
    # Загрузки слота: вложения вопросов идут через них, как у files.
    uploads: UploadBench

    @property
    def connection(self) -> Connection:
        """The slot's connection to the home, as the tables' owner."""
        return self.run_slot.claimed.connections[HOME]

    @asynccontextmanager
    async def sweeping(self) -> AsyncIterator[HomeTransactions]:
        """Transactions as the workers open them: a sweep's listing may take the sweep role."""
        shape = ProcessShape(role=ProcessRole.WORKERS)
        async with open_database_access(slot_urls(self.run_slot), shape) as workers:
            yield workers.transactions

    async def attachment(self, person: uuid.UUID, name: str, body: bytes, kind: str) -> str:
        """A ready `leo_attachment` upload of the person: its id."""
        principal = Principal(person, HOME, 0)
        request = UploadRequest(UploadPurpose.LEO_ATTACHMENT, name, kind, len(body))
        view = await self.uploads.service.create(principal, request)
        [link] = view.links
        async with httpx.AsyncClient() as client:
            put = await client.put(
                link.request.url, content=body, headers=dict(link.request.headers)
            )
        assert put.status_code == 200, put.text
        await self.uploads.service.complete(principal, view.id)
        return str(view.id)

    async def thread(self, person: uuid.UUID, home: Home = HOME) -> str:
        """A new thread of the person: its id."""
        answer = await self.http.post(
            "/v1/agent/threads",
            json={"scope": {"kind": "personal"}},
            headers=bearer((home, person)) | {"Idempotency-Key": uuid.uuid4().hex},
        )
        assert answer.status_code == 201, answer.text
        return str(answer.json()["id"])

    async def ask(
        self,
        person: uuid.UUID,
        thread: str,
        text: str = "What is Shosai?",
        *,
        key: str | None = None,
        home: Home = HOME,
        **body: object,
    ) -> httpx.Response:
        """A turn and its whole stream."""
        key = key or uuid.uuid4().hex
        return await self.http.post(
            f"/v1/agent/threads/{thread}/turns",
            json={"text": text, **body},
            headers=bearer((home, person)) | {"Idempotency-Key": key},
            timeout=WAIT,
        )


def stream_of(answer: httpx.Response) -> list[tuple[str, int, Mapping[str, Any]]]:
    """The events of an SSE body: kind, number and data; comments skipped."""
    events = []
    for block in answer.text.split("\n\n"):
        fields = dict(
            line.split(": ", 1) for line in block.splitlines() if line and not line.startswith(":")
        )
        if "event" in fields:
            events.append((fields["event"], int(fields["id"]), json.loads(fields["data"])))
    return events


@pytest_asyncio.fixture
async def turn_bench(
    homes: DatabaseAccess,
    valkey: Redis,
    run_slot: RunSlot,
    upload_bench: UploadBench,
    bench_doubles: BenchDoubles,
) -> AsyncIterator[TurnBench]:
    """Turns over the slot's homes and Valkey, with one agent worker alive in the fleet."""
    terms, model, queue, meetings = Terms(), ScriptedModel(), InlineQueue(), Meetings()
    ports = PortDirectory()
    ports.install(
        [
            AUTHENTICATOR.bind(BearerOfTheTest()),
            ADMIN_GATE.bind(AdminSession()),
            MEMBERSHIP_READER.bind(MembershipDirectory()),
            TOKEN_ALLOWANCE.bind(terms),
            CONSENT_READER.bind(terms),
            ACCOUNT_PROFILE_READER.bind(Profiles()),
            MEETING_READER.bind(meetings),
            WORKSPACE_READER.bind(WorkspaceDirectory()),
            UPLOADS.bind(upload_bench.claims),
            *(FRICTION_JUDGE.bind(judge) for judge in bench_doubles.judges),
            *(TURN_ROUTER.bind(router) for router in bench_doubles.routers),
            *(TURN_EFFORT_JUDGE.bind(judge) for judge in bench_doubles.efforts),
            *(INJECTION_JUDGE.bind(judge) for judge in bench_doubles.injections),
            *memory_bindings(bench_doubles.memories),
        ]
    )
    registry = CollectorRegistry()
    effects = EffectLedger(EffectKeyMetrics(registry))
    run_log, leases, fleet = RunLog(valkey), ThreadLeases(valkey), Fleet(valkey)
    tail, runs = LogTail(valkey, run_log), RunRegistry(leases, fleet)
    outbox = EventOutbox(EventTypes([*AGENT.events]))
    metrics, spans = RunMetrics(registry), InMemorySpanExporter()
    tracing = TracerProvider(shutdown_on_exit=False)
    tracing.add_span_processor(SimpleSpanProcessor(spans))
    tracer = tracing.get_tracer("shosai.agent")
    telemetry = RunTelemetry(metrics, tracer)
    pages, tools = ResultPages(homes.transactions, ports), bench_doubles.tools
    catalog = AgentToolCatalog()
    catalog.install([*core_tools(pages), *tools.bound()])
    sources = RunSources(homes.transactions, ports)
    cards = ActionCards(catalog, ports)
    judging = FrictionJudging(ports, cards, homes.transactions)
    tool_parts = ToolParts(
        pages, sources, asyncio.Semaphore(4), ToolMetrics(registry), tracer,
        ActionProposer(homes.transactions, cards, judging=judging),
    )  # fmt: skip
    frames = TurnSaver(valkey)
    parts = EngineParts(
        homes.transactions, model, ROUTE, run_log, leases, fleet, runs, outbox,
        turn_graph(frames), frames, ContextBuilder(ports),
        TurnRouting(ToolRegistry(catalog), ports), tool_parts, telemetry,
        AttachmentReader(homes.transactions, (upload_bench.objects, DocumentReader(), pages)),
        QUICK, ports,
    )  # fmt: skip
    queue.engine = RunEngine(parts)
    threads = Threads(homes.transactions, (ports, effects))
    starter = TurnStarter(
        TurnParts(
            homes.transactions, ports, effects, RateLimiter(valkey, KeyValueMetrics(registry)),
            queue, run_log, leases, fleet, threads, frames,
        ),
        limit=GENEROUS,
    )  # fmt: skip
    history, streams = (
        History(homes.transactions, threads, cards),
        RunStreams(homes.transactions, (run_log, tail), leases, metrics, bench_doubles.silence),
    )
    routers = tuple(
        router
        for mount in (person_mount(ports), operator_mount(ports))
        for router in (
            build_threads_router((threads, history), mount),
            build_turns_router((starter, streams), mount),
        )
    )
    await fleet.alive("bench-worker")
    try:
        async with client_of(build_probe_app(extra=routers).app) as http:
            yield TurnBench(
                http, homes, valkey, model, queue, terms, parts, run_slot, meetings,
                (registry, spans), tools, catalog, ports, upload_bench,
            )  # fmt: skip
            await queue.settle()
    finally:
        await tail.close()
        await runs.close()
