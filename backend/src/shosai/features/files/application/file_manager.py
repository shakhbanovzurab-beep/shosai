"""A person's File Manager: list, register uploads, edit, copy, delete, Leo's use (steps 4, 6).

Every read goes through `visible_files` (the access policy, nothing hidden); edits are the
owner's, on their own files. Registering claims ready File Manager uploads in one
transaction — a repeat answers the same files. A copy is a new row on the same object
(FL-D4), counts against the limit and starts without its own Leo switch. A deletion hides
the file at once, frees its bytes and tells knowledge and workspaces (FL-D5); the purge
removes it 7 days later. A change that may start or stop Leo's use goes through `LeoUse`.
"""

from dataclasses import dataclass, replace
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
from shosai.features.files.application.deletion import hide_file
from shosai.features.files.application.file_views import (
    QUEUED,
    FileView,
    FolderView,
    LeoUseView,
    file_views,
    folder_view,
)
from shosai.features.files.application.leo_use import (
    LeoUse,
    candidate,
    leo_folders,
    leo_not_used,
    leo_unreadable,
    own_folders,
    unused,
)
from shosai.features.files.application.upload_claims import UploadClaims
from shosai.features.files.application.uploads import storage_refusal
from shosai.features.files.application.visibility import visible_files
from shosai.features.files.contracts.events import FileUploaded, LeoReindexRequested
from shosai.features.files.domain.kinds import kind_of, leo_readable
from shosai.features.files.domain.leo import LeoShift, knowledge_limit
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
    leo: bool | None = None

    @property
    def may_start_leo(self) -> bool:
        """Whether Leo may start using the file: a rename changes what Leo can read."""
        return self.leo is True or self.move or self.name is not None

    @property
    def touches_leo(self) -> bool:
        """Whether Leo's use of the file may change at all."""
        return self.leo is not None or self.may_start_leo


class FileManager:
    """The person's own files."""

    def __init__(
        self,
        transactions: HomeTransactions,
        services: tuple[PortDirectory, EventOutbox, UploadClaims, LeoUse],
    ) -> None:
        self._transactions = transactions
        self._ports, self._outbox, self._claims, self._leo = services

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
        self,
        principal: Principal,
        upload_ids: list[UUID],
        folder_id: UUID | None,
        *,
        leo: bool = False,
    ) -> list[FileView]:
        """Turn ready File Manager uploads into files; a repeat answers the same files."""
        if not 0 < len(upload_ids) <= FILES_PER_REQUEST:
            raise AppError("upload_count", HTTPStatus.UNPROCESSABLE_CONTENT)
        # Новые файлы Leo использует только по переключателю или по папке.
        touches_leo = leo or folder_id is not None
        limit = await self._leo.limit(principal) if touches_leo else None
        async with self._transactions.begin(principal.scope()) as session:
            if touches_leo:
                await self._leo.hold(session, principal.user_id)
            folders = list(await session.scalars(own_folders(principal.user_id)))
            check_folder(folders, folder_id)
            records: list[StorageFileRecord] = []
            made: list[StorageFileRecord] = []
            for upload_id in upload_ids:
                record, new = await self._file_of(session, principal, upload_id, (folder_id, leo))
                records.append(record)
                if new:
                    made.append(record)
            in_leo = leo_folders(folders)
            shift = LeoShift.of((unused(r), candidate(r, in_leo)) for r in made)
            await self._leo.settle(session, principal.user_id, shift, limit)
            return await file_views(session, self._ports, records, in_leo)

    async def update(self, principal: Principal, file_id: UUID, changes: FileChanges) -> FileView:
        """Rename, move, star a file or switch Leo's use of it."""
        limit = await self._leo.limit(principal) if changes.may_start_leo else None
        async with self._transactions.begin(principal.scope()) as session:
            if changes.touches_leo:
                await self._leo.hold(session, principal.user_id)
            record = await self._own(session, principal, file_id)
            folders = list(await session.scalars(own_folders(principal.user_id)))
            in_leo = leo_folders(folders)
            before = candidate(record, in_leo)
            if changes.name is not None and changes.name != record.name:
                record.name = changes.name
                record.modified_at = datetime.now(UTC)
            if changes.move:
                check_folder(folders, changes.folder_id)
                record.folder_id = changes.folder_id
            if changes.starred is not None:
                record.starred = changes.starred
            if changes.leo is not None:
                if changes.leo and not leo_readable(record.name, record.size_bytes):
                    raise leo_unreadable()
                record.leo_on = changes.leo
                # Включив файл сам, человек снимает удержание FL-D10 — в пределах лимита.
                record.leo_held = record.leo_held and not changes.leo
            await session.flush()
            shift = LeoShift.of([(before, candidate(record, in_leo))])
            await self._leo.settle(session, principal.user_id, shift, limit)
            [view] = await file_views(session, self._ports, [record], in_leo)
        return view

    async def copy(self, principal: Principal, file_id: UUID, name: str | None) -> FileView:
        """A new file on the same object in the source's folder; it counts against the limit."""
        snapshot = await self._ports.get(ENTITLEMENTS).snapshot(principal.home, principal.user_id)
        limit = limit_bytes(snapshot.limits.file_manager_gb)
        async with self._transactions.begin(principal.scope()) as session:
            await self._leo.hold(session, principal.user_id)
            await usage_store.lock(session, principal.user_id)
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
                leo_on=False, created_at=datetime.now(UTC), modified_at=source.modified_at,
            )  # fmt: skip
            session.add(copy)
            await session.flush()
            in_leo = leo_folders(list(await session.scalars(own_folders(principal.user_id))))
            shift = LeoShift.of([(unused(copy), candidate(copy, in_leo))])
            await self._leo.settle(
                session,
                principal.user_id,
                shift,
                knowledge_limit(snapshot.limits.knowledge_base_mb),
            )
            [view] = await file_views(session, self._ports, [copy], in_leo)
        return view

    async def reindex(self, principal: Principal, file_id: UUID) -> FileView:
        """Ask Leo to read a file it uses again; the answer shows it queued."""
        async with self._transactions.begin(principal.scope()) as session:
            record = await self._own(session, principal, file_id)
            in_leo = leo_folders(list(await session.scalars(own_folders(principal.user_id))))
            if not candidate(record, in_leo).used:
                raise leo_not_used()
            event = LeoReindexRequested(file_id=record.id, user_id=principal.user_id)
            await self._outbox.add(session, event)
            [view] = await file_views(session, self._ports, [record], in_leo)
        return view if view.leo is None else replace(view, leo=LeoUseView(view.leo.via, QUEUED))

    async def delete(self, principal: Principal, file_id: UUID) -> None:
        """Hide the file now, free its bytes and tell those who used it (FL-D5)."""
        async with self._transactions.begin(principal.scope()) as session:
            await usage_store.lock(session, principal.user_id)
            record = await self._own(session, principal, file_id)
            await hide_file(session, self._outbox, record, datetime.now(UTC))

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

    async def _file_of(
        self,
        session: AsyncSession,
        principal: Principal,
        upload_id: UUID,
        placement: tuple[UUID | None, bool],
    ) -> tuple[StorageFileRecord, bool]:
        """The file of the upload, and whether it is new; a repeat keeps the file as it is."""
        existing = await session.get(StorageFileRecord, upload_id)
        if existing is not None and existing.user_id == principal.user_id:
            if existing.deleted_at is not None:
                raise file_gone()
            return existing, False
        folder_id, leo = placement
        claimed = await self._claims.claim(session, upload_id, UploadPurpose.FILE_MANAGER)
        if leo and not leo_readable(claimed.filename, claimed.size_bytes):
            raise leo_unreadable()
        now = datetime.now(UTC)
        record = StorageFileRecord(
            id=upload_id, user_id=principal.user_id, folder_id=folder_id, name=claimed.filename,
            content_type=claimed.content_type, size_bytes=claimed.size_bytes,
            object_key=claimed.object_key, leo_on=leo, created_at=now, modified_at=now,
        )  # fmt: skip
        session.add(record)
        await session.flush()
        event = FileUploaded(
            file_id=record.id, user_id=principal.user_id, size_bytes=record.size_bytes,
            kind=kind_of(record.name).value,
        )  # fmt: skip
        await self._outbox.add(session, event)
        return record, True


def check_folder(folders: list[FileFolderRecord], folder_id: UUID | None) -> None:
    """The folder named is one of the person's, or the root."""
    if folder_id is not None and all(folder.id != folder_id for folder in folders):
        raise folder_gone()
