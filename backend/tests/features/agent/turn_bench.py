"""Turns end to end over the slot's homes and Valkey (agent step 5a).

The API's routes admit and stream; the `agent` queue is an inline worker that drives a sent
turn at once in the background, unless the bench holds it to play a lost worker; the model is
a script of pieces, with a pause or a gate between them and an optional failure at the end.
The plan's token decision and the person's consent are doubles the test sets.
"""

import json
import uuid
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Final

import httpx
import pytest_asyncio
from prometheus_client import CollectorRegistry
from redis.asyncio import Redis

from shosai.core.ai.calls import ModelRef, ModelRoute, Provider
from shosai.core.config.roles import ProcessRole
from shosai.core.db.transactions import HomeTransactions
from shosai.core.events.catalog import EventTypes
from shosai.core.events.outbox import EventOutbox
from shosai.core.idempotency.ledger import EffectLedger
from shosai.core.idempotency.metrics import EffectKeyMetrics
from shosai.core.kernel.homes import Home
from shosai.core.kv.metrics import KeyValueMetrics
from shosai.core.kv.rate_limits import RateLimit, RateLimiter
from shosai.core.ports.directory import PortDirectory
from shosai.features.agent.application.history import History
from shosai.features.agent.application.model_stream import Pace
from shosai.features.agent.application.run_context import ContextBuilder
from shosai.features.agent.application.run_engine import EngineParts, RunEngine
from shosai.features.agent.application.run_registry import RunRegistry
from shosai.features.agent.application.run_streams import RunStreams
from shosai.features.agent.application.threads import Threads
from shosai.features.agent.application.turn_commit import TurnParts
from shosai.features.agent.application.turn_start import TurnStarter
from shosai.features.agent.channels.http.threads import build_threads_router
from shosai.features.agent.channels.http.turns import build_turns_router
from shosai.features.agent.infrastructure.fleet import Fleet
from shosai.features.agent.infrastructure.log_tail import LogTail
from shosai.features.agent.infrastructure.run_log import RunLog
from shosai.features.agent.infrastructure.thread_lease import ThreadLeases
from shosai.features.agent.infrastructure.turn_graph import turn_graph
from shosai.features.agent.module import AGENT
from shosai.features.billing.contracts import TOKEN_ALLOWANCE
from shosai.features.identity.contracts import (
    ACCOUNT_PROFILE_READER,
    AUTHENTICATOR,
    CONSENT_READER,
)
from shosai.features.notes.contracts import MEETING_READER
from shosai.features.workspaces.contracts import MEMBERSHIP_READER
from shosai.features.workspaces.infrastructure.membership_reader import MembershipDirectory
from tests.core.web.probe_app import build_probe_app, client_of
from tests.features.agent.turn_doubles import (
    WAIT,
    InlineQueue,
    Meetings,
    Profiles,
    ScriptedModel,
    Terms,
)
from tests.features.billing.people_bench import BearerOfTheTest, bearer
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
SILENCE: Final = timedelta(seconds=1)
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
    homes: DatabaseAccess, valkey: Redis, run_slot: RunSlot
) -> AsyncIterator[TurnBench]:
    """Turns over the slot's homes and Valkey, with one agent worker alive in the fleet."""
    terms, model, queue, meetings = Terms(), ScriptedModel(), InlineQueue(), Meetings()
    ports = PortDirectory()
    ports.install(
        [
            AUTHENTICATOR.bind(BearerOfTheTest()),
            MEMBERSHIP_READER.bind(MembershipDirectory()),
            TOKEN_ALLOWANCE.bind(terms),
            CONSENT_READER.bind(terms),
            ACCOUNT_PROFILE_READER.bind(Profiles()),
            MEETING_READER.bind(meetings),
        ]
    )
    registry = CollectorRegistry()
    effects = EffectLedger(EffectKeyMetrics(registry))
    run_log, leases, fleet = RunLog(valkey), ThreadLeases(valkey), Fleet(valkey)
    tail, runs = LogTail(valkey, run_log), RunRegistry(leases, fleet)
    outbox = EventOutbox(EventTypes([*AGENT.events]))
    parts = EngineParts(
        homes.transactions, model, ROUTE, run_log, leases, fleet, runs, outbox, turn_graph(),
        ContextBuilder(ports), QUICK,
    )  # fmt: skip
    queue.engine = RunEngine(parts)
    threads = Threads(homes.transactions, (ports, effects))
    starter = TurnStarter(
        TurnParts(
            homes.transactions, ports, effects, RateLimiter(valkey, KeyValueMetrics(registry)),
            queue, run_log, leases, fleet, threads,
        ),
        limit=GENEROUS,
    )  # fmt: skip
    routers = (
        build_threads_router((threads, History(homes.transactions, threads)), ports),
        build_turns_router(
            (starter, RunStreams(homes.transactions, (run_log, tail), leases, SILENCE)), ports
        ),
    )
    await fleet.alive("bench-worker")
    try:
        async with client_of(build_probe_app(extra=routers).app) as http:
            yield TurnBench(http, homes, valkey, model, queue, terms, parts, run_slot, meetings)
            await queue.settle()
    finally:
        await tail.close()
        await runs.close()
