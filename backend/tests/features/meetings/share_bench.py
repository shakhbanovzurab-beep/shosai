"""Share links over the slot's homes: the keeper's routes and the public page (step 13).

The clock is the test's, so expiry is checked without waiting; the rate limits run over the
slot's Valkey. Meetings are written with `native_bench.meeting`, participants and links by
the helpers here, in either home.
"""

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx
import pytest_asyncio
from prometheus_client import CollectorRegistry
from redis.asyncio import Redis

from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.kv.metrics import KeyValueMetrics
from shosai.core.kv.rate_limits import RateLimiter
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import ACCOUNT_PROFILE_READER, AUTHENTICATOR
from shosai.features.meetings.application.share_links import ShareLinks
from shosai.features.meetings.application.shared_links import SharedLinks
from shosai.features.meetings.application.shared_pages import SharedPages
from shosai.features.meetings.channels.http.share_links import build_share_links_router
from shosai.features.meetings.channels.http.shared import build_shared_router
from shosai.features.meetings.infrastructure.meeting_records import ParticipantRecord
from shosai.features.workspaces.application.access_policy import WorkspaceAccessPolicy
from shosai.features.workspaces.contracts import ACCESS_POLICY
from shosai.features.workspaces.infrastructure.audit_log import WorkspaceAuditLog
from tests.core.web.probe_app import build_probe_app, client_of
from tests.features.billing.entitlement_bench import Clock
from tests.features.billing.people_bench import BearerOfTheTest
from tests.features.meetings.library_bench import OUTBOX
from tests.features.meetings.native_bench import People
from tests.harness.database_access import DatabaseAccess


@dataclass(frozen=True, slots=True)
class ShareBench:
    """The routes, the homes, the people and the clock."""

    http: httpx.AsyncClient
    homes: DatabaseAccess
    people: People
    clock: Clock

    async def participants(
        self, owner: uuid.UUID, meeting_id: uuid.UUID, people: list[tuple[str | None, str | None]]
    ) -> None:
        """Participants `(name, email)` of the person's meeting."""
        async with self.homes.transactions.begin(TenancyScope(Home.EU, owner)) as session:
            session.add_all(
                ParticipantRecord(
                    id=uuid.uuid4(), session_id=meeting_id, user_id=owner, name=name,
                    email=email, source="added",
                )
                for name, email in people
            )  # fmt: skip


@pytest_asyncio.fixture
async def share_bench(homes: DatabaseAccess, valkey: Redis) -> AsyncIterator[ShareBench]:
    """The share link routes over the slot's homes and Valkey."""
    ports, people, clock = PortDirectory(), People(), Clock()
    ports.install(
        [
            AUTHENTICATOR.bind(BearerOfTheTest()),
            ACCESS_POLICY.bind(WorkspaceAccessPolicy(OUTBOX, WorkspaceAuditLog())),
            ACCOUNT_PROFILE_READER.bind(people),
        ]
    )
    limiter = RateLimiter(valkey, KeyValueMetrics(CollectorRegistry()))
    pages = SharedPages(homes.transactions, (SharedLinks(homes.transactions, clock), ports), clock)
    routers = (
        build_share_links_router(ShareLinks(homes.transactions, ports, clock), ports),
        build_shared_router(pages, limiter),
    )
    async with client_of(build_probe_app(extra=routers).app) as http:
        yield ShareBench(http, homes, people, clock)
