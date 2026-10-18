"""A person's File Manager: list, register uploads, edit, copy, delete, download (files step 4).

Every read goes through `visible_files` (the access policy, nothing hidden); edits are the
owner's, on their own files. Registering claims ready File Manager uploads in one
transaction — a repeat answers the same files. A copy is a new row on the same object
(FL-D4) and counts against the limit. A deletion hides the file at once, frees its bytes
and tells knowledge and workspaces (FL-D5); the purge removes it 7 days later.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from http import HTTPStatus
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.ids import new_id
from shosai.core.ports.directory import PortDirectory
from shosai.features.billing.contracts import ENTITLEMENTS
from shosai.features.files.application.file_views import (
    FileView,
    FolderView,
    file_views,
    folder_view,
)
from shosai.features.files.application.upload_claims import UploadClaims
from shosai.features.files.application.uploads import storage_refusal
from shosai.features.files.application.visibility import visible_files
from shosai.features.files.contracts.events import FileDeleted, FileUploaded
from shosai.features.files.domain.kinds import kind_of
from shosai.features.files.domain.names import copy_name
from shosai.features.files.domain.purposes import FILES_PER_REQUEST, UploadPurpose
from shosai.features.files.domain.quota import limit_bytes
from shosai.features.files.infrastructure import usage_store
from shosai.features.files.infrastructure.file_records import FileFolderRecord, StorageFileRecord
from shosai.features.identity.contracts import Principal
from shosai.features.workspaces.contracts import ACCESS_POLICY, Viewer


def file_gone() -> AppError:
    """No such file the person may use."""
    return AppError("file_not_found", HTTPStatus.NOT_FOUND)


def folder_gone() -> AppError:
    """The folder named is not the person's any more."""
    return AppError("folder_not_found", HTTPStatus.CONFLICT)


@dataclass(frozen=True, slots=True)
class FileChanges:
    """What the owner changes; `move` says whether `folder_id` applies (None is the root)."""

    name: str | None = None
    move: bool = False
    folder_id: UUID | None = None
    starred: bool | None = None


class FileManager:
    """The person's own files."""

    def __init__(
        self,
        transactions: HomeTransactions,
        services: tuple[PortDirectory, EventOutbox, UploadClaims],
    ) -> None:
        self._transactions = transactions
        self._ports, self._outbox, self._claims = services

    async def listing(self, principal: Principal) -> tuple[list[FolderView], list[FileView]]:
        """The person's folders by name and files newest first."""
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            folders = list(await session.scalars(own_folders(principal.user_id)))
            files = list(
                await session.scalars(
                    self._own_files(principal).order_by(StorageFileRecord.modified_at.desc())
                )
            )
            views = await file_views(session, self._ports, files, leo_folders(folders))
        return [folder_view(folder) for folder in folders], views

    async def register(
        self, principal: Principal, upload_ids: list[UUID], folder_id: UUID | None
    ) -> list[FileView]:
        """Turn ready File Manager uploads into files; a repeat answers the same files."""
        if not 0 < len(upload_ids) <= FILES_PER_REQUEST:
            raise AppError("upload_count", HTTPStatus.UNPROCESSABLE_CONTENT)
        async with self._transactions.begin(principal.scope()) as session:
            await self._check_folder(session, principal, folder_id)
            records = [
                await self._file_of(session, principal, upload_id, folder_id)
                for upload_id in upload_ids
            ]
            folders = list(await session.scalars(own_folders(principal.user_id)))
            return await file_views(session, self._ports, records, leo_folders(folders))

    async def update(self, principal: Principal, file_id: UUID, changes: FileChanges) -> FileView:
        """Rename, move or star one of the person's files."""
        async with self._transactions.begin(principal.scope()) as session:
            record = await self._own(session, principal, file_id)
            if changes.name is not None and changes.name != record.name:
                record.name = changes.name
                record.modified_at = datetime.now(UTC)
            if changes.move:
                await self._check_folder(session, principal, changes.folder_id)
                record.folder_id = changes.folder_id
            if changes.starred is not None:
                record.starred = changes.starred
            await session.flush()
            folders = list(await session.scalars(own_folders(principal.user_id)))
            [view] = await file_views(session, self._ports, [record], leo_folders(folders))
        return view

    async def copy(self, principal: Principal, file_id: UUID, name: str | None) -> FileView:
        """A new file on the same object, right after the source; it counts against the limit."""
        snapshot = await self._ports.get(ENTITLEMENTS).snapshot(principal.home, principal.user_id)
        limit = limit_bytes(snapshot.limits.file_manager_gb)
        async with self._transactions.begin(principal.scope()) as session:
            source = await self._own(session, principal, file_id)
            if not await usage_store.charge(session, principal.user_id, source.size_bytes, limit):
                raise storage_refusal(limit)
            taken = set(await session.scalars(select(StorageFileRecord.name).where(
                StorageFileRecord.user_id == principal.user_id,
                StorageFileRecord.deleted_at.is_(None),
                StorageFileRecord.folder_id.is_(None) if source.folder_id is None
                else StorageFileRecord.folder_id == source.folder_id,
            )))  # fmt: skip
            copy = StorageFileRecord(
                id=new_id(), user_id=principal.user_id, folder_id=source.folder_id,
                name=name or copy_name(source.name, taken), content_type=source.content_type,
                size_bytes=source.size_bytes, object_key=source.object_key, sha256=source.sha256,
                created_at=datetime.now(UTC), modified_at=source.modified_at,
            )  # fmt: skip
            session.add(copy)
            await session.flush()
            [view] = await file_views(session, self._ports, [copy], frozenset())
        return view

    async def delete(self, principal: Principal, file_id: UUID) -> None:
        """Hide the file now, free its bytes and tell those who used it (FL-D5)."""
        async with self._transactions.begin(principal.scope()) as session:
            record = await self._own(session, principal, file_id)
            record.deleted_at = datetime.now(UTC)
            await usage_store.free(session, principal.user_id, record.size_bytes)
            await self._outbox.add(
                session, FileDeleted(file_id=record.id, user_id=principal.user_id)
            )

    def _own_files(self, principal: Principal) -> Select[StorageFileRecord]:
        viewer = Viewer(principal.user_id)
        return visible_files(self._ports.get(ACCESS_POLICY), viewer).where(
            StorageFileRecord.user_id == principal.user_id, StorageFileRecord.org_id.is_(None)
        )

    async def _own(
        self, session: AsyncSession, principal: Principal, file_id: UUID
    ) -> StorageFileRecord:
        record = await session.scalar(
            self._own_files(principal).where(StorageFileRecord.id == file_id).with_for_update()
        )
        if record is None:
            raise file_gone()
        return record

    async def _check_folder(
        self, session: AsyncSession, principal: Principal, folder_id: UUID | None
    ) -> None:
        if folder_id is None:
            return
        found = await session.scalar(
            own_folders(principal.user_id).where(FileFolderRecord.id == folder_id)
        )
        if found is None:
            raise folder_gone()

    async def _file_of(
        self, session: AsyncSession, principal: Principal, upload_id: UUID, folder_id: UUID | None
    ) -> StorageFileRecord:
        existing = await session.get(StorageFileRecord, upload_id)
        if existing is not None and existing.user_id == principal.user_id:
            if existing.deleted_at is not None:
                raise file_gone()
            return existing
        claimed = await self._claims.claim(session, upload_id, UploadPurpose.FILE_MANAGER)
        now = datetime.now(UTC)
        record = StorageFileRecord(
            id=upload_id, user_id=principal.user_id, folder_id=folder_id, name=claimed.filename,
            content_type=claimed.content_type, size_bytes=claimed.size_bytes,
            object_key=claimed.object_key, created_at=now, modified_at=now,
        )  # fmt: skip
        session.add(record)
        await session.flush()
        event = FileUploaded(
            file_id=record.id, user_id=principal.user_id, size_bytes=record.size_bytes,
            kind=kind_of(record.name).value,
        )  # fmt: skip
        await self._outbox.add(session, event)
        return record


def own_folders(user_id: UUID) -> Select[FileFolderRecord]:
    """The person's folders by name."""
    return (
        select(FileFolderRecord)
        .where(FileFolderRecord.user_id == user_id)
        .order_by(FileFolderRecord.name, FileFolderRecord.id)
    )


def leo_folders(folders: list[FileFolderRecord]) -> frozenset[UUID]:
    """The folders whose files Leo uses."""
    return frozenset(folder.id for folder in folders if folder.leo)
