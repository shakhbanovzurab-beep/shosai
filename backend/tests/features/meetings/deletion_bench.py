"""Meetings' deletion over the slot's homes and buckets: routes, support, the purge, the audit.

The bench builds the cabinet's, the native and support's routes like the slice does, with
billing's real minutes meter for the tombstones, identity's operator journal for the audit,
and an admin gate that admits the test's cookie. The purge runs as the workers do, so its
listing may take the sweep role.
"""

import uuid
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass

import httpx
import pytest_asyncio
from sqlalchemy import select

from shosai.core.config.roles import ProcessRole
from shosai.core.events.catalog import EventTypes
from shosai.core.events.outbox import EventOutbox
from shosai.core.events.records import OutboxMessage
from shosai.core.events.subscriptions import ReceivedEvent
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.core.storage.port import ObjectStorage
from shosai.features.billing.application.minutes import MinutesMeter
from shosai.features.billing.contracts import USAGE_TOMBSTONES
from shosai.features.identity.application.operator_journal import OperatorJournal
from shosai.features.identity.channels.subscriptions import audit_operator_action
from shosai.features.identity.contracts import (
    ADMIN_COOKIE,
    ADMIN_GATE,
    AUTHENTICATOR,
    OPERATOR_AUDIT,
    OperatorActed,
)
from shosai.features.identity.module import IDENTITY
from shosai.features.meetings.application.deletion import MeetingDeletion
from shosai.features.meetings.application.hidden_meetings import HiddenMeetings
from shosai.features.meetings.application.library import MeetingLibrary
from shosai.features.meetings.application.support_meetings import SupportMeetings
from shosai.features.meetings.channels.http.admin_meetings import build_admin_meetings_router
from shosai.features.meetings.channels.http.meetings import build_meetings_router
from shosai.features.meetings.channels.http.native_me_sessions import (
    build_native_me_sessions_router,
)
from shosai.features.meetings.infrastructure.run_objects import RunObjects
from shosai.features.meetings.module import MEETINGS
from shosai.features.workspaces.application.access_policy import WorkspaceAccessPolicy
from shosai.features.workspaces.contracts import ACCESS_POLICY
from shosai.features.workspaces.infrastructure.audit_log import WorkspaceAuditLog
from shosai.features.workspaces.module import WORKSPACES
from tests.core.storage.adapters import slot_storage
from tests.core.web.probe_app import build_probe_app, client_of
from tests.features.billing.entitlement_bench import Clock, EntitlementBench
from tests.features.billing.people_bench import BearerOfTheTest
from tests.harness.connections import fetch_rows
from tests.harness.database_access import (
    DatabaseAccess,
    ProcessShape,
    open_database_access,
    slot_urls,
)
from tests.harness.run_slot import RunSlot
from tests.harness.shared_services import SlotBucket

ADMIN_SESSION = "admin-of-the-test"
# Сессия админа — заголовком: cookies отдельного запроса httpx объявил устаревшими.
ADMIN: dict[str, str] = {"Cookie": f"{ADMIN_COOKIE}={ADMIN_SESSION}"}


class AdmitsTheTest:
    """The admin gate: the test's cookie is a live admin session."""

    async def admitted(self, cookie: str | None) -> bool:
        """Whether the cookie is the test's."""
        return cookie == ADMIN_SESSION


@dataclass(frozen=True, slots=True)
class DeletionBench:
    """The routes' client and what the tests drive and read back."""

    http: httpx.AsyncClient
    homes: DatabaseAccess
    run_slot: RunSlot
    ports: PortDirectory
    support: SupportMeetings
    objects: RunObjects
    storage: Mapping[Home, ObjectStorage]
    clock: Clock

    @asynccontextmanager
    async def purge(self) -> AsyncIterator[HiddenMeetings]:
        """The purge as the workers run it: its listing may take the sweep role."""
        shape = ProcessShape(role=ProcessRole.WORKERS)
        async with open_database_access(slot_urls(self.run_slot), shape) as workers:
            objects = RunObjects(workers.transactions, self.storage)
            yield HiddenMeetings(workers.transactions, (self.ports, objects), self.clock)

    async def audit(self, home: Home, user_id: uuid.UUID) -> list[tuple[str, uuid.UUID | None]]:
        """The person's audit events, delivered to identity's EU log as its consumer does."""
        scope = TenancyScope(home, user_id)
        async with self.homes.transactions.begin(scope, read_only=True) as session:
            found = list(
                await session.execute(
                    select(OutboxMessage.id, OutboxMessage.occurred_at, OutboxMessage.payload)
                    .where(OutboxMessage.event_type == OperatorActed.event_type)
                    .order_by(OutboxMessage.id)
                )
            )
        for event_id, occurred_at, payload in found:
            event = OperatorActed.model_validate(payload)
            received = ReceivedEvent(event, event_id, 1, occurred_at, scope)
            async with self.homes.transactions.begin(TenancyScope(Home.EU)) as session:
                await audit_operator_action(session, received)
        rows = await fetch_rows(
            self.run_slot.claimed.connections[Home.EU],
            "SELECT action, subject_id FROM operator_audit_events"
            " WHERE target_user_id = %s ORDER BY created_at",
            (user_id,),
        )
        return [(row["action"], row["subject_id"]) for row in rows]


@pytest_asyncio.fixture
async def deletion_bench(
    entitlements: EntitlementBench, run_slot: RunSlot, buckets: Mapping[Home, SlotBucket]
) -> AsyncIterator[DeletionBench]:
    """The deletion's routes, support and the purge over the slot's homes and buckets."""
    transactions, clock = entitlements.homes.transactions, entitlements.clock
    outbox = EventOutbox(EventTypes([*MEETINGS.events, *WORKSPACES.events, *IDENTITY.events]))
    ports = PortDirectory()
    meter = MinutesMeter(transactions, (entitlements.snapshots, ports), clock)
    ports.install(
        [
            AUTHENTICATOR.bind(BearerOfTheTest()),
            ACCESS_POLICY.bind(WorkspaceAccessPolicy(outbox, WorkspaceAuditLog())),
            USAGE_TOMBSTONES.bind(meter),
            OPERATOR_AUDIT.bind(OperatorJournal(outbox)),
            ADMIN_GATE.bind(AdmitsTheTest()),
        ]
    )
    storage: dict[Home, ObjectStorage] = {
        home: slot_storage(bucket).objects for home, bucket in buckets.items()
    }
    library = MeetingLibrary(transactions, ports, clock)
    deletion = MeetingDeletion(transactions, (ports, outbox), clock)
    support = SupportMeetings(transactions, (ports, outbox), clock)
    routers = (
        build_native_me_sessions_router((library, deletion), ports),
        build_meetings_router((library, deletion), ports),
        build_admin_meetings_router(support, ports),
    )
    async with client_of(build_probe_app(extra=routers).app) as http:
        yield DeletionBench(
            http, entitlements.homes, run_slot, ports, support,
            RunObjects(transactions, storage), storage, clock,
        )  # fmt: skip
