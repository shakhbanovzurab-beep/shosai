"""The thread routes over the slot's homes, with workspaces' membership reader (agent step 4).

Workspaces and memberships are written straight into the slot as workspaces keeps them;
the purge and the erasure run as the workers run them, whose listings take the sweep role.
"""

import uuid
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Final

import httpx
import pytest_asyncio
from prometheus_client import CollectorRegistry

from shosai.core.agent_tools.catalog import AgentToolCatalog
from shosai.core.config.roles import ProcessRole
from shosai.core.idempotency.ledger import EffectLedger
from shosai.core.idempotency.metrics import EffectKeyMetrics
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.agent.application.action_cards import ActionCards
from shosai.features.agent.application.departures import Departures
from shosai.features.agent.application.history import History
from shosai.features.agent.application.threads import Threads
from shosai.features.agent.channels.http.callers import person_mount
from shosai.features.agent.channels.http.threads import build_threads_router
from shosai.features.agent.infrastructure.thread_records import AgentMessageRecord
from shosai.features.identity.contracts import AUTHENTICATOR
from shosai.features.notes.infrastructure.meeting_records import MEETING_RESOURCE
from shosai.features.workspaces.contracts import MEMBERSHIP_READER
from shosai.features.workspaces.infrastructure.membership_reader import MembershipDirectory
from tests.core.web.probe_app import build_probe_app, client_of
from tests.features.billing.people_bench import BearerOfTheTest, bearer
from tests.harness.connections import Connection
from tests.harness.database_access import (
    DatabaseAccess,
    ProcessShape,
    open_database_access,
    slot_urls,
)
from tests.harness.run_slot import RunSlot
from tests.support.access_model import MemberRow, WorkspaceRow, World
from tests.support.isolation import write_world

HOME: Final = Home.EU
# Сейчас, а не фиксированная дата: разделы сообщений создаются от месяца прогона вперёд.
START: Final = datetime.now(UTC).replace(microsecond=0)
LEAVE: Final = (
    "UPDATE memberships SET state = 'removed', removed_at = now(), removal_reason = 'left'"
    " WHERE org_id = %s AND user_id = %s"
)
RETURN: Final = (
    "UPDATE memberships SET state = 'active', removed_at = NULL, removal_reason = NULL"
    " WHERE org_id = %s AND user_id = %s"
)


@dataclass
class TestClock:
    """The test's time, moved by hand."""

    now: datetime = START

    def __call__(self) -> datetime:
        return self.now

    def advance(self, by: timedelta) -> None:
        """Move the time forward."""
        self.now += by


@dataclass(frozen=True, slots=True)
class ThreadBench:
    """The routes, the slot's homes and the workers' purge, on one clock."""

    http: httpx.AsyncClient
    homes: DatabaseAccess
    run_slot: RunSlot
    ports: PortDirectory
    clock: TestClock = field(default_factory=TestClock)

    @property
    def connection(self) -> Connection:
        """The slot's connection to the home, as the tables' owner."""
        return self.run_slot.claimed.connections[HOME]

    async def call(
        self,
        person: uuid.UUID,
        method: str,
        path: str,
        json: object = None,
        headers: Mapping[str, str] | None = None,
    ) -> httpx.Response:
        """A request of the person to the routes."""
        sent = bearer((HOME, person)) | dict(headers or {})
        return await self.http.request(method, path, json=json, headers=sent)

    async def thread(self, person: uuid.UUID, org: uuid.UUID | None = None) -> str:
        """A new thread of the person in Personal or a workspace: its id."""
        scope = (
            {"kind": "personal"} if org is None else {"kind": "workspace", "workspace_id": str(org)}
        )
        answer = await self.http.post(
            "/v1/agent/threads",
            json={"scope": scope},
            headers=bearer((HOME, person)) | {"Idempotency-Key": uuid.uuid4().hex},
        )
        assert answer.status_code == 201, answer.text
        return str(answer.json()["id"])

    async def workspace(self, org: uuid.UUID, owner: uuid.UUID, *members: uuid.UUID) -> None:
        """An active workspace with its owner and members."""
        world = World(
            workspaces=[WorkspaceRow(org, "active")],
            members=[
                MemberRow(uuid.uuid4(), org, owner, "owner", "active"),
                *(MemberRow(uuid.uuid4(), org, member, "member", "active") for member in members),
            ],
        )
        await write_world(self.connection, MEETING_RESOURCE, world)

    async def leave(self, org: uuid.UUID, member: uuid.UUID) -> None:
        """The member's membership ends."""
        await self.connection.execute(LEAVE, (org, member))

    async def come_back(self, org: uuid.UUID, member: uuid.UUID) -> None:
        """The member's membership is active again."""
        await self.connection.execute(RETURN, (org, member))

    async def message(
        self, person: uuid.UUID, thread: str, role: str, moment: datetime, text: str = "…"
    ) -> str:
        """A row of the thread, written as a turn writes it: its id. A `round` is the model's
        message with its tool calls."""
        message_id = uuid.uuid4()
        calls = [{"id": "call-1", "name": "notes__search", "arguments": "{}"}]
        stored = "assistant" if role == "round" else role
        status = "done" if stored == "assistant" else None
        tool = ("call-1", "notes.search") if role == "tool" else (None, None)
        async with self.homes.transactions.begin(TenancyScope(HOME, person)) as session:
            session.add(
                AgentMessageRecord(
                    id=message_id, created_at=moment, thread_id=uuid.UUID(thread),
                    user_id=person, role=stored, status=status, text=text,
                    tool_call_id=tool[0], tool_name=tool[1],
                    tool_calls=calls if role == "round" else None,
                )
            )  # fmt: skip
        return str(message_id)

    @asynccontextmanager
    async def departures(self) -> AsyncIterator[Departures]:
        """Departures as the workers run them: their listings may take the sweep role."""
        shape = ProcessShape(role=ProcessRole.WORKERS)
        async with open_database_access(slot_urls(self.run_slot), shape) as workers:
            yield Departures(workers.transactions, self.ports, self.clock)


@pytest_asyncio.fixture
async def thread_bench(homes: DatabaseAccess, run_slot: RunSlot) -> AsyncIterator[ThreadBench]:
    """The thread routes over the slot's homes."""
    ports = PortDirectory()
    ports.install(
        [AUTHENTICATOR.bind(BearerOfTheTest()), MEMBERSHIP_READER.bind(MembershipDirectory())]
    )
    clock = TestClock()
    effects = EffectLedger(EffectKeyMetrics(CollectorRegistry()))
    threads = Threads(homes.transactions, (ports, effects), clock)
    # Тредам без хода карточки не нужны: каталог инструментов пуст.
    cards = ActionCards(AgentToolCatalog(), ports)
    router = build_threads_router(
        (threads, History(homes.transactions, threads, cards)), person_mount(ports)
    )
    async with client_of(build_probe_app(extra=(router,)).app) as http:
        yield ThreadBench(http, homes, run_slot, ports, clock)
