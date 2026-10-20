"""Meetings over the slot's homes with billing's real minutes and workspaces' access policy.

The bench builds the lifecycle and its routes like the slice does, with billing's minutes
meter counting the meetings through the slice's own binding, and the test's bearer tokens.
"""

import uuid
from collections.abc import AsyncIterator, Collection, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import httpx
import pytest_asyncio
from prometheus_client import CollectorRegistry
from sqlalchemy import select

from shosai.core.config.roles import ProcessRole
from shosai.core.events.catalog import EventTypes
from shosai.core.events.outbox import EventOutbox
from shosai.core.events.records import OutboxMessage
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.billing.application.minutes import MinutesMeter
from shosai.features.billing.contracts import MEETING_MINUTES, MINUTES_ALLOWANCE, USAGE_TOMBSTONES
from shosai.features.identity.contracts import AUTHENTICATOR
from shosai.features.notes.application.lifecycle import MeetingLifecycle
from shosai.features.notes.application.live_meetings import LiveMeetingBinder
from shosai.features.notes.application.live_transcript import LiveTranscript
from shosai.features.notes.application.minutes import MeetingMinutesCount
from shosai.features.notes.application.runs_view import RunViews
from shosai.features.notes.application.sweeps import MeetingSweeps
from shosai.features.notes.channels.http.native_sessions import build_native_sessions_router
from shosai.features.notes.channels.http.runs import build_runs_router
from shosai.features.notes.contracts import LIVE_SIGNAL
from shosai.features.notes.infrastructure.meeting_records import TranscriptLineRecord
from shosai.features.notes.infrastructure.metrics import MeetingMetrics
from shosai.features.notes.infrastructure.transcript_metrics import TranscriptMetrics
from shosai.features.notes.module import NOTES
from shosai.features.workspaces.application.access_policy import WorkspaceAccessPolicy
from shosai.features.workspaces.contracts import ACCESS_POLICY
from shosai.features.workspaces.infrastructure.audit_log import WorkspaceAuditLog
from shosai.features.workspaces.module import WORKSPACES
from tests.core.web.probe_app import build_probe_app, client_of
from tests.features.billing.entitlement_bench import Clock, EntitlementBench
from tests.features.billing.people_bench import BearerOfTheTest
from tests.harness.database_access import (
    DatabaseAccess,
    ProcessShape,
    open_database_access,
    slot_urls,
)
from tests.harness.run_slot import RunSlot


@dataclass
class CaptureSignal:
    """What capture would report: the last audio and the highest line shown, per meeting."""

    audio: dict[uuid.UUID, datetime] = field(default_factory=dict)
    shown: dict[uuid.UUID, int] = field(default_factory=dict)

    async def last_audio(self, meeting_ids: Collection[uuid.UUID]) -> Mapping[uuid.UUID, datetime]:
        """The meetings capture holds."""
        return {m: self.audio[m] for m in meeting_ids if m in self.audio}

    async def highest_shown(self, meeting_id: uuid.UUID) -> int | None:
        """The highest line shown, if capture holds the meeting."""
        return self.shown.get(meeting_id)


@dataclass(frozen=True, slots=True)
class MeetingBench:
    """The routes' client, the lifecycle and what the tests read back."""

    http: httpx.AsyncClient
    homes: DatabaseAccess
    lifecycle: MeetingLifecycle
    meter: MinutesMeter
    count: MeetingMinutesCount
    clock: Clock
    transcript: LiveTranscript
    binder: LiveMeetingBinder
    signal: CaptureSignal
    registry: CollectorRegistry
    metrics: TranscriptMetrics
    ports: PortDirectory
    run_slot: RunSlot

    @asynccontextmanager
    async def sweeps(self) -> AsyncIterator[MeetingSweeps]:
        """The sweeps as the workers run them: their transactions may take the sweep role."""
        async with open_database_access(
            slot_urls(self.run_slot), ProcessShape(role=ProcessRole.WORKERS)
        ) as workers:
            yield MeetingSweeps(
                workers.transactions,
                (self.ports, self.lifecycle, self.metrics),
                self.clock,
            )

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
async def meeting_bench(
    entitlements: EntitlementBench, run_slot: RunSlot
) -> AsyncIterator[MeetingBench]:
    """The native start and end, §10's end and runs over the slot's homes."""
    transactions = entitlements.homes.transactions
    outbox = EventOutbox(EventTypes([*NOTES.events, *WORKSPACES.events]))
    ports = PortDirectory()
    signal = CaptureSignal()
    count = MeetingMinutesCount(entitlements.clock)
    meter = MinutesMeter(transactions, (entitlements.snapshots, ports), entitlements.clock)
    ports.install(
        [
            AUTHENTICATOR.bind(BearerOfTheTest()),
            ACCESS_POLICY.bind(WorkspaceAccessPolicy(outbox, WorkspaceAuditLog())),
            MINUTES_ALLOWANCE.bind(meter),
            USAGE_TOMBSTONES.bind(meter),
            MEETING_MINUTES.bind(count),
            LIVE_SIGNAL.bind(signal),
        ]
    )
    registry = CollectorRegistry()
    lifecycle = MeetingLifecycle(
        transactions, (ports, outbox, MeetingMetrics(registry)), entitlements.clock
    )
    metrics = TranscriptMetrics(registry)
    routers = (
        build_native_sessions_router(lifecycle, ports),
        build_runs_router((lifecycle, RunViews(transactions, ports)), ports),
    )
    async with client_of(build_probe_app(extra=routers).app) as http:
        yield MeetingBench(
            http, entitlements.homes, lifecycle, meter, count, entitlements.clock,
            LiveTranscript(transactions, metrics), LiveMeetingBinder(ports), signal,
            registry, metrics, ports, run_slot,
        )  # fmt: skip
