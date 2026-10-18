"""A person's flat folders: create, rename, delete (the cabinet's File Manager).

Deleting a folder moves its files to the root, because the foreign key sets their folder
to nothing, and the files stay. Folder names follow the file name rules, and two folders
may share a name.
"""

from datetime import UTC, datetime
from http import HTTPStatus
from uuid import UUID

from sqlalchemy import delete

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.ids import new_id
from shosai.features.files.application.file_views import FolderView, folder_view
from shosai.features.files.infrastructure.file_records import FileFolderRecord
from shosai.features.identity.contracts import Principal


def folder_not_found() -> AppError:
    """No such folder of the person."""
    return AppError("folder_not_found", HTTPStatus.NOT_FOUND)


class Folders:
    """The person's folders."""

    def __init__(self, transactions: HomeTransactions) -> None:
        self._transactions = transactions

    async def create(self, principal: Principal, name: str) -> FolderView:
        """A new empty folder."""
        now = datetime.now(UTC)
        record = FileFolderRecord(
            id=new_id(), user_id=principal.user_id, name=name, created_at=now, updated_at=now
        )
        async with self._transactions.begin(principal.scope()) as session:
            session.add(record)
        return folder_view(record)

    async def rename(self, principal: Principal, folder_id: UUID, name: str) -> FolderView:
        """A folder's new name."""
        async with self._transactions.begin(principal.scope()) as session:
            record = await session.get(FileFolderRecord, folder_id, with_for_update=True)
            if record is None or record.user_id != principal.user_id:
                raise folder_not_found()
            record.name, record.updated_at = name, datetime.now(UTC)
        return folder_view(record)

    async def delete(self, principal: Principal, folder_id: UUID) -> None:
        """Remove the folder; its files move to the root."""
        async with self._transactions.begin(principal.scope()) as session:
            removed = await session.scalar(
                delete(FileFolderRecord)
                .where(
                    FileFolderRecord.id == folder_id, FileFolderRecord.user_id == principal.user_id
                )
                .returning(FileFolderRecord.id)
            )
        if removed is None:
            raise folder_not_found()
