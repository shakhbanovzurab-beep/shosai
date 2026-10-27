"""The facts' routes over the slot's homes, with the doubles of the readers they call."""

import uuid
from collections.abc import AsyncIterator, Collection, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import httpx
import pytest_asyncio
from prometheus_client import CollectorRegistry
from redis.asyncio import Redis
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.idempotency.ledger import EffectLedger
from shosai.core.idempotency.metrics import EffectKeyMetrics
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import AUTHENTICATOR
from shosai.features.memory.application.fact_changes import FactChanges
from shosai.features.memory.application.fact_list import FactLists
from shosai.features.memory.application.fact_restore import FactRestore
from shosai.features.memory.application.switch import MemorySwitch
from shosai.features.memory.channels.http.facts import build_memory_router
from shosai.features.memory.infrastructure.metrics import MemoryMetrics
from shosai.features.memory.infrastructure.records import MemoryFactRecord
from shosai.features.notes.contracts import (
    MEETING_READER,
    MeetingFacts,
    MeetingNotFoundError,
    TranscriptPage,
)
from shosai.features.notes.domain.meetings import MeetingStatus
from shosai.features.workspaces.contracts import MEMBERSHIP_READER, ActiveMembership, Viewer
from shosai.features.workspaces.domain.roles import WorkspaceRole
from tests.core.web.probe_app import build_probe_app, client_of
from tests.features.billing.people_bench import BearerOfTheTest
from tests.harness.database_access import DatabaseAccess

START = datetime(2026, 10, 27, 9, tzinfo=UTC)


@dataclass
class Spaces:
    """The workspaces each person belongs to, as the test sets them."""

    of: dict[uuid.UUID, set[uuid.UUID]] = field(default_factory=dict)

    async def active(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> tuple[ActiveMembership, ...]:
        """The person's memberships."""
        del session
        return tuple(
            ActiveMembership(org_id, uuid.uuid4(), WorkspaceRole.MEMBER)
            for org_id in self.of.get(user_id, set())
        )

    async def has_memberships(self, session: AsyncSession, user_id: uuid.UUID) -> bool:
        """Whether the person belongs anywhere."""
        return bool(await self.active(session, user_id))

    async def members(
        self, session: AsyncSession, org_id: uuid.UUID, user_ids: Collection[uuid.UUID]
    ) -> Mapping[uuid.UUID, ActiveMembership]:
        """The members of a workspace among the people."""
        del session
        return {
            user_id: ActiveMembership(org_id, uuid.uuid4(), WorkspaceRole.MEMBER)
            for user_id in user_ids
            if org_id in self.of.get(user_id, set())
        }


@dataclass
class Meetings:
    """Meetings the people may read, by id, with their titles."""

    titles: dict[uuid.UUID, str] = field(default_factory=dict)

    async def facts(
        self, session: AsyncSession, viewer: Viewer, meeting_ids: Collection[uuid.UUID]
    ) -> Mapping[uuid.UUID, MeetingFacts]:
        """The readable ones among the ids."""
        del session
        return {
            meeting_id: MeetingFacts(
                meeting_id=meeting_id, user_id=viewer.user_id, org_id=None,
                title=self.titles[meeting_id], status=MeetingStatus.COMPLETED,
                started_at=START, ended_at=START, seconds=60, participants=(), summary=None,
            )
            for meeting_id in meeting_ids
            if meeting_id in self.titles
        }  # fmt: skip

    async def transcript(
        self, home: Home, viewer: Viewer, meeting_id: uuid.UUID, cursor: str | None, limit: int
    ) -> TranscriptPage:
        """No transcript is read by memory's lists."""
        del home, viewer, meeting_id, cursor, limit
        raise MeetingNotFoundError

    async def readable(
        self, session: AsyncSession, viewer: Viewer, meeting_ids: Collection[uuid.UUID]
    ) -> frozenset[uuid.UUID]:
        """The readable ones among the ids."""
        del session, viewer
        return frozenset(meeting_id for meeting_id in meeting_ids if meeting_id in self.titles)


@dataclass(frozen=True, slots=True)
class FactsBench:
    """The routes, the doubles behind them and the slot's homes."""

    http: httpx.AsyncClient
    homes: DatabaseAccess
    spaces: Spaces
    meetings: Meetings
    registry: CollectorRegistry

    async def add(self, person: uuid.UUID, rows: Sequence[Mapping[str, object]]) -> list[uuid.UUID]:
        """Facts of the person in the Russian home, a minute apart in the given order."""
        ids = [uuid.uuid4() for _ in rows]
        values = [
            {
                "id": fact_id, "user_id": person, "kind": "fact", "statement": "Leads product",
                "source_kind": "user_statement", "status": "active",
                "created_at": START + timedelta(minutes=index),
            } | dict(row)
            for index, (fact_id, row) in enumerate(zip(ids, rows, strict=True))
        ]  # fmt: skip
        async with self.homes.transactions.begin(TenancyScope(Home.RU, person)) as session:
            await session.execute(insert(MemoryFactRecord), values)
        return ids


@pytest_asyncio.fixture
async def facts_bench(homes: DatabaseAccess, valkey: Redis) -> AsyncIterator[FactsBench]:
    spaces, meetings = Spaces(), Meetings()
    ports = PortDirectory()
    ports.install(
        [
            AUTHENTICATOR.bind(BearerOfTheTest()),
            MEMBERSHIP_READER.bind(spaces),
            MEETING_READER.bind(meetings),
        ]
    )
    lists = FactLists(homes.transactions, ports)
    registry = CollectorRegistry()
    effects = EffectLedger(EffectKeyMetrics(registry))
    changes = FactChanges(homes.transactions, (lists, effects, valkey, MemoryMetrics(registry)))
    switch = MemorySwitch(homes.transactions)
    restore = FactRestore(homes.transactions, (lists, valkey))
    router = build_memory_router((lists, changes, switch, restore), ports)
    async with client_of(build_probe_app(extra=(router,)).app) as http:
        yield FactsBench(http, homes, spaces, meetings, registry)
