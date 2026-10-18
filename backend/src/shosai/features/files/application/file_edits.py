"""Edits of one of the person's own files, inside a transaction the caller opened.

The File Manager's routes and Leo's write tools apply the same rules through these: a
rename, a move, a star and Leo's switch in `edit`, the deletion (hidden for 7 days, FL-D5)
in `remove`. The caller reads the knowledge limit before its transaction; inside it the
person's locks go in one order — the Leo lock, the usage row, then the file.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from http import HTTPStatus
from uuid import UUID

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.errors import AppError
from shosai.core.ports.directory import PortDirectory
from shosai.features.files.application.deletion import hide_file
from shosai.features.files.application.file_views import FileView, file_views
from shosai.features.files.application.leo_use import (
    LeoUse,
    candidate,
    leo_folders,
    leo_unreadable,
    own_folders,
)
from shosai.features.files.application.visibility import visible_files
from shosai.features.files.domain.kinds import leo_readable
from shosai.features.files.domain.leo import LeoShift
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


def check_folder(folders: list[FileFolderRecord], folder_id: UUID | None) -> None:
    """The folder named is one of the person's, or the root."""
    if folder_id is not None and all(folder.id != folder_id for folder in folders):
        raise folder_gone()


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


class FileEdits:
    """The person's own files, edited in the caller's transaction."""

    def __init__(self, ports: PortDirectory, outbox: EventOutbox, leo: LeoUse) -> None:
        self._ports, self._outbox, self._leo = ports, outbox, leo

    def own_files(self, principal: Principal) -> Select[StorageFileRecord]:
        """The person's own personal files they may see."""
        viewer = Viewer(principal.user_id)
        return visible_files(self._ports.get(ACCESS_POLICY), viewer).where(
            StorageFileRecord.user_id == principal.user_id, StorageFileRecord.org_id.is_(None)
        )

    async def own(
        self, session: AsyncSession, principal: Principal, file_id: UUID
    ) -> StorageFileRecord:
        """One of the person's own files, locked for the transaction; 404 otherwise."""
        record = await session.scalar(
            self.own_files(principal).where(StorageFileRecord.id == file_id).with_for_update()
        )
        if record is None:
            raise file_gone()
        return record

    async def edit(
        self,
        session: AsyncSession,
        principal: Principal,
        target: tuple[UUID, FileChanges],
        limit: int | None,
    ) -> FileView:
        """Rename, move, star the file or switch Leo's use of it; `limit` is the knowledge
        limit, read before the transaction when the change may start Leo's use."""
        file_id, changes = target
        if changes.touches_leo:
            await self._leo.hold(session, principal.user_id)
        record = await self.own(session, principal, file_id)
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

    async def remove(self, session: AsyncSession, principal: Principal, file_id: UUID) -> None:
        """Hide the file now, free its bytes and tell those who used it (FL-D5)."""
        await usage_store.lock(session, principal.user_id)
        record = await self.own(session, principal, file_id)
        await hide_file(session, self._outbox, record, datetime.now(UTC))
