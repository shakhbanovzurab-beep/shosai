"""A person's flat folders: create, rename, switch Leo's use, delete (the cabinet's File Manager).

Leo uses every readable file in a folder it reads, files added later included. Switching
a folder starts or stops Leo's use of its readable files that are not switched on by
themselves; deleting a folder moves its files to the root, because the foreign key sets
their folder to nothing, and Leo stops using those it read only through the folder.
Folder names follow the file name rules, and two folders may share a name.
"""

from datetime import UTC, datetime
from http import HTTPStatus
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.ids import new_id
from shosai.core.ports.directory import PortDirectory
from shosai.features.files.application.file_views import FolderView, folder_view
from shosai.features.files.application.leo_use import LeoUse, candidate
from shosai.features.files.application.visibility import visible_files
from shosai.features.files.domain.leo import LeoShift
from shosai.features.files.infrastructure.file_records import FileFolderRecord, StorageFileRecord
from shosai.features.identity.contracts import Principal
from shosai.features.workspaces.contracts import ACCESS_POLICY, Viewer


def folder_not_found() -> AppError:
    """No such folder of the person."""
    return AppError("folder_not_found", HTTPStatus.NOT_FOUND)


class Folders:
    """The person's folders."""

    def __init__(
        self, transactions: HomeTransactions, services: tuple[PortDirectory, LeoUse]
    ) -> None:
        self._transactions = transactions
        self._ports, self._leo = services

    async def create(self, principal: Principal, name: str) -> FolderView:
        """A new empty folder; Leo does not read it until it is switched on."""
        now = datetime.now(UTC)
        record = FileFolderRecord(
            id=new_id(), user_id=principal.user_id, name=name, created_at=now, updated_at=now
        )
        async with self._transactions.begin(principal.scope()) as session:
            session.add(record)
        return folder_view(record)

    async def update(
        self, principal: Principal, folder_id: UUID, *, name: str | None, leo: bool | None
    ) -> FolderView:
        """A folder's new name, or Leo's use of its files switched on or off."""
        limit = await self._leo.limit(principal) if leo else None
        async with self._transactions.begin(principal.scope()) as session:
            if leo is not None:
                await self._leo.hold(session, principal.user_id)
            record = await self._own(session, principal, folder_id)
            if name is not None and name != record.name:
                record.name, record.updated_at = name, datetime.now(UTC)
            if leo is not None and leo != record.leo:
                files = await self._files_in(session, principal, folder_id)
                shift = self._switch(record, files, on=leo)
                record.updated_at = datetime.now(UTC)
                await session.flush()
                await self._leo.settle(session, principal.user_id, shift, limit)
        return folder_view(record)

    async def delete(self, principal: Principal, folder_id: UUID) -> None:
        """Remove the folder; its files move to the root and Leo stops reading them through it."""
        async with self._transactions.begin(principal.scope()) as session:
            await self._leo.hold(session, principal.user_id)
            record = await self._own(session, principal, folder_id)
            shift = LeoShift()
            if record.leo:
                shift = self._switch(record, await self._files_in(session, principal, folder_id))
            await session.delete(record)
            await session.flush()
            await self._leo.settle(session, principal.user_id, shift, None)

    @staticmethod
    def _switch(
        record: FileFolderRecord, files: list[StorageFileRecord], *, on: bool = False
    ) -> LeoShift:
        """Set the folder's switch; the shift of its files from the old switch to the new."""
        was = frozenset({record.id}) if record.leo else frozenset()
        now = frozenset({record.id}) if on else frozenset()
        record.leo = on
        return LeoShift.of((candidate(file, was), candidate(file, now)) for file in files)

    async def _own(
        self, session: AsyncSession, principal: Principal, folder_id: UUID
    ) -> FileFolderRecord:
        record = await session.get(FileFolderRecord, folder_id, with_for_update=True)
        if record is None or record.user_id != principal.user_id:
            raise folder_not_found()
        return record

    async def _files_in(
        self, session: AsyncSession, principal: Principal, folder_id: UUID
    ) -> list[StorageFileRecord]:
        """The person's visible files in the folder."""
        viewer = Viewer(principal.user_id)
        query = visible_files(self._ports.get(ACCESS_POLICY), viewer).where(
            StorageFileRecord.user_id == principal.user_id,
            StorageFileRecord.folder_id == folder_id,
        )
        return list(await session.scalars(query))
