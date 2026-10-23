"""The `files.held_objects` binding: objects files holds for another slice (ADR 0064).

The holder's transaction is the owner's: its person for a personal row; a workspace's is
not included until files' step 8b opens workspace storage (FL-D6). An upload is held once,
its reservation settled by the claim; a File Manager file is held on its own object, its
row locked against the purge after the person's usage row (the order of usage_store), and
its bytes charged. A release frees the bytes and records the deletion of every key no file
row or held object names; the holder discards them after its commit.
"""

from collections.abc import Collection, Mapping
from typing import Final
from uuid import UUID

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions, transaction_info
from shosai.core.kernel.homes import Home
from shosai.core.kernel.ids import new_id
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.core.storage.port import Disposition, ObjectStorage
from shosai.core.tasks.errors import TaskQueueUnavailableError
from shosai.features.billing.contracts import ENTITLEMENTS
from shosai.features.files.application.account_data import unnamed
from shosai.features.files.application.file_edits import file_gone
from shosai.features.files.application.preview_task import (
    MAKE_PREVIEW,
    PreviewPayload,
    PreviewSender,
)
from shosai.features.files.application.upload_claims import UploadClaims
from shosai.features.files.application.uploads import storage_refusal
from shosai.features.files.application.visibility import visible_files
from shosai.features.files.contracts import UploadNotClaimableError
from shosai.features.files.contracts.held_objects import HeldObject, ObjectLink
from shosai.features.files.domain.kinds import opens_inline
from shosai.features.files.domain.previews import PREVIEW_TYPE, previewable
from shosai.features.files.domain.purposes import PURPOSES, UploadPurpose
from shosai.features.files.domain.quota import limit_bytes
from shosai.features.files.infrastructure import usage_store
from shosai.features.files.infrastructure.download_links import edge_link
from shosai.features.files.infrastructure.file_records import StorageFileRecord
from shosai.features.files.infrastructure.held_records import HeldObjectRecord
from shosai.features.files.infrastructure.object_deleter import ObjectDeleter, record_deletions
from shosai.features.workspaces.contracts import ACCESS_POLICY, Viewer

PENDING: Final = "pending"
log = structlog.stdlib.get_logger(__name__)


class HeldObjectsService:
    """Holds, releases and links the objects of other slices' rows."""

    def __init__(
        self,
        transactions: HomeTransactions,
        ports: PortDirectory,
        storage: tuple[Mapping[Home, ObjectStorage], ObjectDeleter, str | None],
        workers: tuple[PreviewSender, UploadClaims],
    ) -> None:
        self._transactions = transactions
        self._ports = ports
        self._objects, self._deleter, self._base = storage
        self._tasks, self._claims = workers

    async def limit(self, home: Home, user_id: UUID) -> int | None:
        """The person's storage limit in bytes, from their plan."""
        snapshot = await self._ports.get(ENTITLEMENTS).snapshot(home, user_id)
        return limit_bytes(snapshot.limits.file_manager_gb)

    async def from_upload(
        self, session: AsyncSession, upload_id: UUID, purpose: UploadPurpose
    ) -> HeldObject:
        """The person's ready upload of a holding purpose, held once."""
        user_id = _personal_owner(session)
        if not PURPOSES[purpose].held:
            raise UploadNotClaimableError
        # Захват держит строку загрузки: повтор ждёт первую транзакцию и видит её объект.
        claimed = await self._claims.claim(session, upload_id, purpose)
        found = await session.scalar(
            select(HeldObjectRecord).where(HeldObjectRecord.upload_id == upload_id)
        )
        if found is None:
            found = HeldObjectRecord(
                id=upload_id, user_id=user_id, holder=purpose.value, upload_id=upload_id,
                object_key=claimed.object_key, filename=claimed.filename,
                content_type=claimed.content_type, size_bytes=claimed.size_bytes,
                preview_state=PENDING if previewable(claimed.content_type) else "none",
            )  # fmt: skip
            session.add(found)
            await session.flush()
        return _held(found)

    async def from_file(
        self,
        session: AsyncSession,
        viewer: Viewer,
        file_id: UUID,
        hold: tuple[UploadPurpose, int | None],
    ) -> HeldObject:
        """A readable File Manager file held on its object and charged to the owner."""
        purpose, limit = hold
        user_id = _personal_owner(session)
        await usage_store.lock(session, user_id)
        source = await session.scalar(
            visible_files(self._ports.get(ACCESS_POLICY), viewer)
            .where(StorageFileRecord.id == file_id)
            .with_for_update(read=True, of=StorageFileRecord)
        )
        if source is None:
            raise file_gone()
        if not await usage_store.charge(session, user_id, source.size_bytes, limit):
            raise storage_refusal(limit)
        held = HeldObjectRecord(
            id=new_id(), user_id=user_id, holder=purpose.value, object_key=source.object_key,
            filename=source.name, content_type=source.content_type, size_bytes=source.size_bytes,
            preview_state=PENDING if previewable(source.content_type) else "none",
        )  # fmt: skip
        session.add(held)
        await session.flush()
        return _held(held)

    async def release(self, session: AsyncSession, held_ids: Collection[UUID]) -> tuple[str, ...]:
        """Drop the held objects, free their bytes and record the objects left unnamed."""
        if not held_ids:
            return ()
        gone = (
            await session.execute(
                delete(HeldObjectRecord)
                .where(HeldObjectRecord.id.in_(list(held_ids)))
                .returning(
                    HeldObjectRecord.user_id, HeldObjectRecord.org_id, HeldObjectRecord.size_bytes,
                    HeldObjectRecord.object_key, HeldObjectRecord.preview_key,
                )
            )
        ).all()  # fmt: skip
        keys: set[str] = set()
        for user_id, org_id, size_bytes, object_key, preview in gone:
            if org_id is None:
                await usage_store.free(session, user_id, size_bytes)
            keys.update(key for key in (object_key, preview) if key is not None)
        orphaned = await unnamed(session, sorted(keys))
        await record_deletions(session, orphaned)
        return tuple(orphaned)

    async def discard(self, home: Home, keys: Collection[str]) -> None:
        """Delete released objects; what fails waits for files' sweep."""
        await self._deleter.discard(home, list(keys))

    async def links(
        self, scope: TenancyScope, held_ids: Collection[UUID]
    ) -> Mapping[UUID, ObjectLink]:
        """Download links of the held objects, inline when the type opens in the browser."""
        found: dict[UUID, ObjectLink] = {}
        for record in await self._records(scope, held_ids):
            inline = opens_inline(record.content_type)
            signed = await self._objects[scope.home].presign_get(
                record.object_key, filename=record.filename,
                disposition=Disposition.INLINE if inline else Disposition.ATTACHMENT,
                content_type=record.content_type,
            )  # fmt: skip
            url = edge_link(signed.url, scope.home, self._base)
            found[record.id] = ObjectLink(url, signed.expires_at)
        return found

    async def previews(self, scope: TenancyScope, held_ids: Collection[UUID]) -> Mapping[UUID, str]:
        """Links of the previews made so far."""
        found: dict[UUID, str] = {}
        for record in await self._records(scope, held_ids):
            if record.preview_key is None:
                continue
            signed = await self._objects[scope.home].presign_get(
                record.preview_key, filename=f"{record.id}.webp", disposition=Disposition.INLINE,
                content_type=PREVIEW_TYPE,
            )  # fmt: skip
            found[record.id] = edge_link(signed.url, scope.home, self._base)
        return found

    async def _records(
        self, scope: TenancyScope, held_ids: Collection[UUID]
    ) -> list[HeldObjectRecord]:
        """The held objects, read and the transaction closed before any storage call."""
        if not held_ids:
            return []
        async with self._transactions.begin(scope, read_only=True) as session:
            rows = await session.scalars(
                select(HeldObjectRecord).where(HeldObjectRecord.id.in_(list(held_ids)))
            )
            return list(rows)

    async def prepare(self, home: Home, held_ids: Collection[UUID]) -> None:
        """Queue the previews; a queue out of reach leaves them to the sweep's retry."""
        for held_id in held_ids:
            try:
                await self._tasks.send(MAKE_PREVIEW, PreviewPayload(home=home, held_id=held_id))
            except TaskQueueUnavailableError:
                log.warning("Превью не поставлено в очередь: повторит обход", home=home.value)
                return


def _personal_owner(session: AsyncSession) -> UUID:
    """The transaction's person; a workspace's storage is not included until step 8b."""
    scope = transaction_info(session).scope
    if scope.org_id is not None or scope.user_id is None:
        raise storage_refusal(0)
    return scope.user_id


def _held(record: HeldObjectRecord) -> HeldObject:
    return HeldObject(
        id=record.id,
        filename=record.filename,
        content_type=record.content_type,
        size_bytes=record.size_bytes,
        image=previewable(record.content_type),
    )
