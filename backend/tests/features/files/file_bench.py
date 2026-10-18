"""The File Manager over the upload bench: files made from real uploads, the access policy,
the outbox, downloads with an edge base and support's hidden files.
"""

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx
import pytest_asyncio
from prometheus_client import CollectorRegistry
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.events.catalog import EventTypes
from shosai.core.events.outbox import EventOutbox
from shosai.core.events.records import OutboxMessage
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.billing.contracts import ENTITLEMENTS
from shosai.features.files.application.downloads import Downloads
from shosai.features.files.application.file_manager import FileManager
from shosai.features.files.application.file_views import FileView
from shosai.features.files.application.folders import Folders
from shosai.features.files.application.hidden_files import HiddenFiles
from shosai.features.files.application.leo_use import LeoUse
from shosai.features.files.application.quota_watch import QuotaWatch
from shosai.features.files.application.upload_rules import UploadRequest
from shosai.features.files.domain.purposes import UploadPurpose
from shosai.features.files.infrastructure.quota_metrics import QuotaMetrics
from shosai.features.files.infrastructure.upload_records import StorageUsageRecord
from shosai.features.files.module import FILES
from shosai.features.identity.contracts import (
    ACCOUNT_PROFILE_READER,
    ADMIN_GATE,
    AUTHENTICATOR,
    AccountProfile,
    Principal,
)
from shosai.features.workspaces.application.access_policy import WorkspaceAccessPolicy
from shosai.features.workspaces.contracts import ACCESS_POLICY
from shosai.features.workspaces.infrastructure.audit_log import WorkspaceAuditLog
from shosai.features.workspaces.module import WORKSPACES
from tests.core.email.bench import mail_bench
from tests.features.billing.catalogue_bench import BenchGate
from tests.features.billing.people_bench import BearerOfTheTest
from tests.features.files.upload_bench import UploadBench

EDGE = "https://shosai.tech/dl"
PERSON_EMAIL = "person@shosai.example"


class Profiles:
    """Every person of the bench reads English mail at one address."""

    async def profile(self, session: AsyncSession, user_id: uuid.UUID) -> AccountProfile | None:
        """The person's profile with the bench's address."""
        del session, user_id
        return AccountProfile("Person", "en", None, None, PERSON_EMAIL)


@dataclass(frozen=True, slots=True)
class FileBench:
    """The File Manager's services over one slot."""

    uploads: UploadBench
    ports: PortDirectory
    outbox: EventOutbox
    manager: FileManager
    folders: Folders
    downloads: Downloads
    hidden: HiddenFiles
    watch: QuotaWatch
    leo: LeoUse
    registry: CollectorRegistry

    async def uploaded(self, who: Principal, name: str, body: bytes) -> uuid.UUID:
        """A ready File Manager upload of `body`."""
        request = UploadRequest(UploadPurpose.FILE_MANAGER, name, "application/pdf", len(body))
        view = await self.uploads.service.create(who, request)
        [link] = view.links
        async with httpx.AsyncClient() as client:
            answer = await client.put(
                link.request.url, content=body, headers=dict(link.request.headers)
            )
        assert answer.status_code == 200, answer.text
        await self.uploads.service.complete(who, view.id)
        return view.id

    async def file(self, who: Principal, name: str, body: bytes) -> FileView:
        """A file of the person's File Manager, made from a real upload."""
        [view] = await self.manager.register(who, [await self.uploaded(who, name, body)], None)
        return view

    async def used(self, who: Principal) -> int:
        """The person's used bytes."""
        scope = TenancyScope(who.home, who.user_id)
        async with self.uploads.transactions.begin(scope, read_only=True) as session:
            row = await session.get(StorageUsageRecord, who.user_id)
        return 0 if row is None else row.used_bytes

    async def events(self, who: Principal) -> list[str]:
        """The types of the events written for the person, in order."""
        scope = TenancyScope(who.home, who.user_id)
        async with self.uploads.transactions.begin(scope, read_only=True) as session:
            rows = await session.scalars(
                select(OutboxMessage.event_type)
                .where(OutboxMessage.user_id == who.user_id)
                .order_by(OutboxMessage.id)
            )
            return list(rows)

    async def leo_events(self, who: Principal) -> list[tuple[uuid.UUID, bool]]:
        """The person's `files.leo_use.changed` events in order: the file and whether used."""
        scope = TenancyScope(who.home, who.user_id)
        async with self.uploads.transactions.begin(scope, read_only=True) as session:
            payloads = await session.scalars(
                select(OutboxMessage.payload)
                .where(
                    OutboxMessage.user_id == who.user_id,
                    OutboxMessage.event_type == "files.leo_use.changed",
                )
                .order_by(OutboxMessage.id)
            )
            return [(uuid.UUID(str(p["file_id"])), bool(p["used"])) for p in payloads]


@pytest_asyncio.fixture
async def file_bench(upload_bench: UploadBench) -> AsyncIterator[FileBench]:
    """The File Manager over the upload bench; downloads point at the edge, bearer and admin
    sessions are the test's."""
    transactions = upload_bench.transactions
    outbox = EventOutbox(EventTypes([*FILES.events, *WORKSPACES.events]))
    registry = CollectorRegistry()
    ports = PortDirectory()
    policy = WorkspaceAccessPolicy(outbox, WorkspaceAuditLog())
    ports.install([
        ENTITLEMENTS.bind(upload_bench.plan), ACCESS_POLICY.bind(policy),
        AUTHENTICATOR.bind(BearerOfTheTest()), ADMIN_GATE.bind(BenchGate()),
        ACCOUNT_PROFILE_READER.bind(Profiles()),
    ])  # fmt: skip
    mail = mail_bench(transactions, smtp_port=1).port
    watch = QuotaWatch(
        transactions, (ports, outbox, mail, QuotaMetrics(registry)), upload_bench.clock
    )
    leo = LeoUse(ports, outbox)
    yield FileBench(
        uploads=upload_bench,
        ports=ports,
        outbox=outbox,
        manager=FileManager(transactions, (ports, outbox, upload_bench.claims, leo)),
        folders=Folders(transactions, (ports, leo)),
        downloads=Downloads(transactions, (upload_bench.storage.objects, ports), EDGE),
        hidden=HiddenFiles(
            transactions, (outbox, upload_bench.deleter, watch, leo), upload_bench.clock
        ),
        watch=watch,
        leo=leo,
        registry=registry,
    )
