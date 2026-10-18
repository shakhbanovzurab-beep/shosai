"""Uploads straight to the home's bucket: create, resume, complete, cancel (§10; FL-D1).

Create reserves a File Manager upload's declared bytes against the person's plan, starts
the multipart upload on its final key and signs a link per part for its exact length. The
browser PUTs the parts; a replayed part overwrites. Complete assembles the planned parts
and checks the object by `HEAD`: a size other than the declared one is REJECTED, its
object deleted and its reservation released. Every storage call runs outside any
transaction and no body ever passes through the API (§14 rules 1 and 8). States change
by conditional updates, so a completion and the sweep never both win.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Final
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.ids import new_id
from shosai.core.ports.directory import PortDirectory
from shosai.core.storage.errors import StorageRejectedError
from shosai.core.storage.port import MultipartUpload, UploadedPart
from shosai.features.billing.contracts import ENTITLEMENTS
from shosai.features.files.application.upload_links import (
    StorageOfHomes,
    UploadView,
    links_for,
    view_of,
)
from shosai.features.files.application.upload_rules import UploadRequest, checked_request
from shosai.features.files.domain.keys import PersonOwner, file_key, transient_key
from shosai.features.files.domain.purposes import PURPOSES, UploadPurpose
from shosai.features.files.domain.quota import limit_bytes
from shosai.features.files.domain.uploads import (
    UploadState,
    completed_size_matches,
    deadline,
    part_sizes,
)
from shosai.features.files.infrastructure import usage_store
from shosai.features.files.infrastructure.object_deleter import ObjectDeleter, record_deletions
from shosai.features.files.infrastructure.upload_records import UploadRecord
from shosai.features.identity.contracts import Principal

OPEN: Final = (UploadState.PENDING.value, UploadState.READY.value)


def not_found() -> AppError:
    """No such upload of the person."""
    return AppError("upload_not_found", HTTPStatus.NOT_FOUND)


def closed() -> AppError:
    """The upload was rejected, cancelled or expired."""
    return AppError("upload_closed", HTTPStatus.CONFLICT)


class UploadService:
    """The person's uploads."""

    def __init__(
        self,
        transactions: HomeTransactions,
        storage: StorageOfHomes,
        services: tuple[PortDirectory, ObjectDeleter],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._storage = storage
        self._ports, self._deleter = services
        self._clock = clock

    async def create(self, principal: Principal, raw: UploadRequest) -> UploadView:
        """Reserve, start the multipart upload and sign a link per part."""
        request = checked_request(raw)
        counted = PURPOSES[request.purpose].in_file_manager
        limit = await self._limit(principal) if counted else None
        upload_id, now = new_id(), self._clock()
        key = (
            file_key(PersonOwner(principal.user_id), upload_id)
            if counted
            else transient_key(request.purpose, upload_id)
        )
        multipart = await self._storage.uploads[principal.home].create(
            key, content_type=request.content_type
        )
        record = UploadRecord(
            id=upload_id, user_id=principal.user_id, purpose=request.purpose.value,
            object_key=key, multipart_id=multipart.upload_id, filename=request.filename,
            content_type=request.content_type, size_bytes=request.size_bytes,
            state=UploadState.PENDING.value, created_at=now, expires_at=deadline(now),
        )  # fmt: skip
        try:
            async with self._transactions.begin(principal.scope()) as session:
                if counted and not await usage_store.reserve(
                    session, principal.user_id, request.size_bytes, limit
                ):
                    raise storage_refusal(limit)
                session.add(record)
        except Exception:
            await self._storage.uploads[principal.home].abort(multipart)
            raise
        links = await links_for(self._storage.uploads[principal.home], multipart, record, done=())
        return view_of(record, (), links)

    async def status(self, principal: Principal, upload_id: UUID) -> UploadView:
        """The upload's state; while pending, the parts done and links for the rest."""
        record = await self._record(principal, upload_id)
        if record.state != UploadState.PENDING.value:
            return view_of(record, (), ())
        uploads = self._storage.uploads[principal.home]
        multipart = MultipartUpload(record.object_key, record.multipart_id)
        # Хранилище может перечислить повторённую часть дважды: номер считается один раз.
        done = tuple(sorted({part.number for part in await uploads.list_parts(multipart)}))
        return view_of(record, done, await links_for(uploads, multipart, record, done=done))

    async def complete(self, principal: Principal, upload_id: UUID) -> UploadView:
        """Assemble the parts and check the object; READY, or REJECTED over its size."""
        record = await self._record(principal, upload_id)
        if record.state in {UploadState.READY.value, UploadState.CLAIMED.value}:
            return view_of(record, (), ())
        if record.state != UploadState.PENDING.value or self._clock() >= record.expires_at:
            raise closed()
        uploads = self._storage.uploads[principal.home]
        multipart = MultipartUpload(record.object_key, record.multipart_id)
        parts: dict[int, UploadedPart] = {}
        # S3 хранит одну версию части; SeaweedFS после повтора перечисляет обе, новую первой.
        for part in await uploads.list_parts(multipart):
            parts.setdefault(part.number, part)
        planned = range(1, len(part_sizes(record.size_bytes)) + 1)
        if any(number not in parts for number in planned):
            raise AppError("upload_incomplete", HTTPStatus.CONFLICT)
        try:
            await uploads.complete(multipart, [parts[number] for number in planned])
        except StorageRejectedError:
            return await self._reject(principal, record)
        info = await self._storage.objects[principal.home].head(record.object_key)
        if not completed_size_matches(record.size_bytes, None if info is None else info.size):
            return await self._reject(principal, record)
        moved = await self._move(principal, record, UploadState.PENDING, UploadState.READY)
        return view_of(moved, (), ())

    async def cancel(self, principal: Principal, upload_id: UUID) -> None:
        """Abandon an open upload: abort it, release its bytes and delete what was stored."""
        record = await self._record(principal, upload_id)
        if record.state not in OPEN:
            return
        if record.state == UploadState.PENDING.value:
            multipart = MultipartUpload(record.object_key, record.multipart_id)
            await self._storage.uploads[principal.home].abort(multipart)
        await self._close(principal, record, UploadState.EXPIRED)

    async def _reject(self, principal: Principal, record: UploadRecord) -> UploadView:
        return view_of(await self._close(principal, record, UploadState.REJECTED), (), ())

    async def _close(
        self, principal: Principal, record: UploadRecord, to: UploadState
    ) -> UploadRecord:
        """Close an open upload in one transaction; its object goes after the commit."""
        async with self._transactions.begin(principal.scope()) as session:
            closed_record = await move_state(session, record.id, UploadState(record.state), to)
            if closed_record is not None:
                if PURPOSES[UploadPurpose(record.purpose)].in_file_manager:
                    await usage_store.release(session, record.user_id, record.size_bytes)
                await record_deletions(session, [record.object_key])
        if closed_record is None:
            return await self._record(principal, record.id)
        await self._deleter.discard(principal.home, [record.object_key])
        return closed_record

    async def _move(
        self, principal: Principal, record: UploadRecord, source: UploadState, to: UploadState
    ) -> UploadRecord:
        async with self._transactions.begin(principal.scope()) as session:
            moved = await move_state(session, record.id, source, to)
        if moved is None:
            raise closed()
        return moved

    async def _record(self, principal: Principal, upload_id: UUID) -> UploadRecord:
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            record = await session.scalar(
                select(UploadRecord).where(
                    UploadRecord.id == upload_id, UploadRecord.user_id == principal.user_id
                )
            )
        if record is None:
            raise not_found()
        return record

    async def _limit(self, principal: Principal) -> int | None:
        snapshot = await self._ports.get(ENTITLEMENTS).snapshot(principal.home, principal.user_id)
        return limit_bytes(snapshot.limits.file_manager_gb)


def storage_refusal(limit: int | None) -> AppError:
    """A File Manager upload the plan does not cover: not included at all, or over the limit."""
    if limit == 0:
        return AppError("storage_not_included", HTTPStatus.FORBIDDEN)
    return AppError("storage_limit", HTTPStatus.REQUEST_ENTITY_TOO_LARGE)


async def move_state(
    session: AsyncSession, upload_id: UUID, source: UploadState, to: UploadState
) -> UploadRecord | None:
    """Move the upload from `source` to `to` if it is still there; the row, or None."""
    statement = (
        update(UploadRecord)
        .where(UploadRecord.id == upload_id, UploadRecord.state == source.value)
        .values(state=to.value, finished_at=datetime.now(UTC))
        .returning(UploadRecord)
    )
    return await session.scalar(statement)
