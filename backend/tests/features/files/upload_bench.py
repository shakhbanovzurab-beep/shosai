"""Uploads over the slot's homes and buckets, with guards that fail a storage call made
while a transaction is open (§14 rules 1 and 8), and a plan the test sets.
"""

from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.core.storage.errors import ObjectsNotDeletedError
from shosai.core.storage.port import (
    Disposition,
    MultipartUpload,
    MultipartUploads,
    ObjectInfo,
    ObjectStorage,
    ObjectStream,
    PresignedRequest,
    UploadedPart,
)
from shosai.features.billing.contracts import (
    ENTITLEMENTS,
    Audience,
    EntitlementSnapshot,
    EntitlementSource,
    PlanLimits,
)
from shosai.features.files.application.upload_claims import UploadClaims
from shosai.features.files.application.upload_links import StorageOfHomes
from shosai.features.files.application.upload_sweep import UploadSweep
from shosai.features.files.application.uploads import UploadService
from shosai.features.files.infrastructure.object_deleter import ObjectDeleter
from shosai.features.identity.contracts import Principal
from tests.core.storage.adapters import slot_storage
from tests.harness.database_access import DatabaseAccess
from tests.harness.shared_services import SlotBucket

GIB = 1024**3


@dataclass
class Clock:
    """A clock the test moves."""

    now: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __call__(self) -> datetime:
        return self.now


@dataclass
class Plan:
    """The storage the person's plan gives, in GB; None is unlimited."""

    file_manager_gb: int | None = 1

    async def snapshot(self, home: Home, user_id: UUID) -> EntitlementSnapshot:
        """A snapshot with the test's storage limit."""
        del home
        return EntitlementSnapshot(
            user_id=user_id, plan_slug="pro", plan_name="Pro", audience=Audience.INDIVIDUAL,
            paid=True, in_grace=False, paid_until=None,
            limits=PlanLimits(None, self.file_manager_gb, 100), capabilities=frozenset(),
            source=EntitlementSource.PERSONAL, workspace_id=None, version=1,
        )  # fmt: skip


class Guard:
    """Counts open transactions; a storage call while one is open fails the test."""

    def __init__(self) -> None:
        self.open = 0
        # Бакет отказывает в удалении, пока тест не снимет флаг.
        self.failing_deletes = False

    def check(self) -> None:
        """Fail when a transaction is open."""
        assert self.open == 0, "вызов хранилища при открытой транзакции"


class GuardedTransactions:
    """Transactions that tell the guard while they are open."""

    def __init__(self, inner: HomeTransactions, guard: Guard) -> None:
        self._inner, self._guard = inner, guard

    @asynccontextmanager
    async def begin(
        self, scope: TenancyScope, *, read_only: bool = False, sweep: bool = False
    ) -> AsyncIterator[AsyncSession]:
        """The inner transaction, counted."""
        async with self._inner.begin(scope, read_only=read_only, sweep=sweep) as session:
            self._guard.open += 1
            try:
                yield session
            finally:
                self._guard.open -= 1


class GuardedObjects:
    """A bucket's objects; each call first asks the guard."""

    def __init__(self, inner: ObjectStorage, guard: Guard) -> None:
        self._inner, self._guard = inner, guard

    async def head(self, key: str) -> ObjectInfo | None:
        """The object's facts."""
        self._guard.check()
        return await self._inner.head(key)

    def open(self, key: str) -> AbstractAsyncContextManager[ObjectStream]:
        """The object's bytes."""
        self._guard.check()
        return self._inner.open(key)

    async def delete_many(self, keys: Sequence[str]) -> None:
        """Delete the objects; a failure the test set comes first."""
        self._guard.check()
        if self._guard.failing_deletes:
            raise ObjectsNotDeletedError(list(keys), ["InternalError"])
        await self._inner.delete_many(keys)

    async def presign_get(
        self,
        key: str,
        *,
        filename: str,
        disposition: Disposition,
        content_type: str | None = None,
    ) -> PresignedRequest:
        """A download link."""
        self._guard.check()
        return await self._inner.presign_get(
            key, filename=filename, disposition=disposition, content_type=content_type
        )


class GuardedUploads:
    """A bucket's multipart uploads; each call first asks the guard."""

    def __init__(self, inner: MultipartUploads, guard: Guard) -> None:
        self._inner, self._guard = inner, guard

    async def create(self, key: str, *, content_type: str) -> MultipartUpload:
        """Start an upload."""
        self._guard.check()
        return await self._inner.create(key, content_type=content_type)

    async def presign_part(
        self, upload: MultipartUpload, number: int, *, content_length: int
    ) -> PresignedRequest:
        """Sign a part's link."""
        self._guard.check()
        return await self._inner.presign_part(upload, number, content_length=content_length)

    async def upload_part(self, upload: MultipartUpload, number: int, body: bytes) -> UploadedPart:
        """Send a part from the server."""
        self._guard.check()
        return await self._inner.upload_part(upload, number, body)

    async def list_parts(self, upload: MultipartUpload) -> list[UploadedPart]:
        """The parts stored."""
        self._guard.check()
        return await self._inner.list_parts(upload)

    async def complete(self, upload: MultipartUpload, parts: Sequence[UploadedPart]) -> None:
        """Assemble the parts."""
        self._guard.check()
        await self._inner.complete(upload, parts)

    async def abort(self, upload: MultipartUpload) -> None:
        """Abandon the upload."""
        self._guard.check()
        await self._inner.abort(upload)


@dataclass(frozen=True, slots=True)
class UploadBench:
    """The service, its claim and sweep, the raw storage and what the test sets."""

    service: UploadService
    claims: UploadClaims
    storage: StorageOfHomes
    transactions: HomeTransactions
    deleter: ObjectDeleter
    plan: Plan
    clock: Clock
    guard: Guard
    objects: Mapping[Home, ObjectStorage]

    def sweep(self, transactions: HomeTransactions) -> UploadSweep:
        """The sweep over transactions that may run as the sweep role."""
        return UploadSweep(transactions, (self.storage.uploads, self.deleter), self.clock)


def person(home: Home, user_id: UUID) -> Principal:
    return Principal(user_id, home, 0)


@pytest_asyncio.fixture
async def upload_bench(
    homes: DatabaseAccess, buckets: Mapping[Home, SlotBucket]
) -> AsyncIterator[UploadBench]:
    """Uploads over the slot, every storage call guarded."""
    guard = Guard()
    storages = {home: slot_storage(bucket) for home, bucket in buckets.items()}
    objects = {
        home: cast("ObjectStorage", GuardedObjects(s.objects, guard))
        for home, s in storages.items()
    }
    uploads = {
        home: cast("MultipartUploads", GuardedUploads(s.uploads, guard))
        for home, s in storages.items()
    }
    transactions = cast("HomeTransactions", GuardedTransactions(homes.transactions, guard))
    plan, clock = Plan(), Clock()
    ports = PortDirectory()
    ports.install([ENTITLEMENTS.bind(plan)])
    storage = StorageOfHomes(objects, uploads)
    deleter = ObjectDeleter(transactions, objects)
    service = UploadService(transactions, storage, (ports, deleter), clock)
    yield UploadBench(
        service, UploadClaims(clock), storage, transactions, deleter, plan, clock, guard,
        {home: s.objects for home, s in storages.items()},
    )  # fmt: skip
