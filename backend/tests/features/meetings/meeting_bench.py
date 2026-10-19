"""Meetings over the slot's homes with billing's real minutes and workspaces' access policy.

The bench builds the lifecycle and its routes like the slice does, with billing's minutes
meter counting the meetings through meetings' own binding, and the test's bearer tokens.
"""

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime, timedelta

import httpx
import pytest_asyncio
from prometheus_client import CollectorRegistry
from sqlalchemy import select

from shosai.core.events.catalog import EventTypes
from shosai.core.events.outbox import EventOutbox
from shosai.core.events.records import OutboxMessage
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.billing.application.minutes import MinutesMeter
from shosai.features.billing.contracts import MEETING_MINUTES, MINUTES_ALLOWANCE, USAGE_TOMBSTONES
from shosai.features.identity.contracts import AUTHENTICATOR
from shosai.features.meetings.application.lifecycle import MeetingLifecycle
from shosai.features.meetings.application.minutes import MeetingMinutesCount
from shosai.features.meetings.application.runs_view import RunViews
from shosai.features.meetings.channels.http.native_sessions import build_native_sessions_router
from shosai.features.meetings.channels.http.runs import build_runs_router
from shosai.features.meetings.infrastructure.meeting_records import TranscriptLineRecord
from shosai.features.meetings.infrastructure.metrics import MeetingMetrics
from shosai.features.meetings.module import MEETINGS
from shosai.features.workspaces.application.access_policy import WorkspaceAccessPolicy
from shosai.features.workspaces.contracts import ACCESS_POLICY
from shosai.features.workspaces.infrastructure.audit_log import WorkspaceAuditLog
from shosai.features.workspaces.module import WORKSPACES
from tests.core.web.probe_app import build_probe_app, client_of
from tests.features.billing.entitlement_bench import Clock, EntitlementBench
from tests.features.billing.people_bench import BearerOfTheTest
from tests.harness.database_access import DatabaseAccess


@dataclass(frozen=True, slots=True)
class MeetingBench:
    """The routes' client, the lifecycle and what the tests read back."""

    http: httpx.AsyncClient
    homes: DatabaseAccess
    lifecycle: MeetingLifecycle
    meter: MinutesMeter
    count: MeetingMinutesCount
    clock: Clock

    async def spoke(
        self, home: Home, meeting_id: uuid.UUID, started_at: datetime, lines: int
    ) -> None:
        """Store `lines` live lines of a meeting, one a second from its start."""
        async with self.homes.transactions.begin(TenancyScope(home)) as session:
            session.add_all(
                TranscriptLineRecord(
                    session_id=meeting_id, seq=seq, meeting_started_at=started_at,
                    started_at=started_at + timedelta(seconds=seq), start_ms=seq * 1000,
                    duration_ms=800, text="Да.",
                )
                for seq in range(1, lines + 1)
            )  # fmt: skip

    async def events(self, home: Home, event_type: str) -> list[OutboxMessage]:
        """The outbox rows of a type in the home, oldest first."""
        async with self.homes.transactions.begin(TenancyScope(home), read_only=True) as session:
            rows = await session.scalars(
                select(OutboxMessage)
                .where(OutboxMessage.event_type == event_type)
                .order_by(OutboxMessage.occurred_at)
            )
            return list(rows.all())


def bearer(home: Home, user_id: uuid.UUID) -> dict[str, str]:
    """The Authorization header of a person."""
    return {"Authorization": f"Bearer person:{user_id}:{home.value}"}


@pytest_asyncio.fixture
async def meeting_bench(entitlements: EntitlementBench) -> AsyncIterator[MeetingBench]:
    """The native start and end, §10's end and runs over the slot's homes."""
    transactions = entitlements.homes.transactions
    outbox = EventOutbox(EventTypes([*MEETINGS.events, *WORKSPACES.events]))
    ports = PortDirectory()
    count = MeetingMinutesCount(entitlements.clock)
    meter = MinutesMeter(transactions, (entitlements.snapshots, ports), entitlements.clock)
    ports.install(
        [
            AUTHENTICATOR.bind(BearerOfTheTest()),
            ACCESS_POLICY.bind(WorkspaceAccessPolicy(outbox, WorkspaceAuditLog())),
            MINUTES_ALLOWANCE.bind(meter),
            USAGE_TOMBSTONES.bind(meter),
            MEETING_MINUTES.bind(count),
        ]
    )
    lifecycle = MeetingLifecycle(
        transactions, (ports, outbox, MeetingMetrics(CollectorRegistry())), entitlements.clock
    )
    routers = (
        build_native_sessions_router(lifecycle, ports),
        build_runs_router((lifecycle, RunViews(transactions, ports)), ports),
    )
    async with client_of(build_probe_app(extra=routers).app) as http:
        yield MeetingBench(http, entitlements.homes, lifecycle, meter, count, entitlements.clock)
