"""The `files.file_reader` binding: files a viewer may read, for other slices (files step 9).

Both calls start from `visible_files` — the access policy, no deleted file, no file of an
account in its deletion window — so knowledge's indexing and search re-check and the
agent's read tool see exactly what the person may read. `facts` runs in the caller's
transaction; `open` checks access in a short transaction of its own and streams the bytes
from the home's bucket after it ends, holding no session across the storage call.
"""

from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.core.storage.port import ObjectStorage, ObjectStream
from shosai.features.files.application.visibility import visible_files
from shosai.features.files.contracts import FileFacts, FileUnreadableError
from shosai.features.files.domain.kinds import kind_of, leo_readable
from shosai.features.files.infrastructure.file_records import StorageFileRecord
from shosai.features.workspaces.contracts import ACCESS_POLICY, Viewer


class FilesReader:
    """Metadata and bytes of the files a viewer may read."""

    def __init__(
        self,
        transactions: HomeTransactions,
        services: tuple[PortDirectory, Mapping[Home, ObjectStorage]],
    ) -> None:
        self._transactions = transactions
        self._ports, self._objects = services

    async def facts(
        self, session: AsyncSession, viewer: Viewer, file_ids: Sequence[UUID]
    ) -> Mapping[UUID, FileFacts]:
        """The readable ones among `file_ids`; the others are absent."""
        if not file_ids:
            return {}
        query = visible_files(self._ports.get(ACCESS_POLICY), viewer).where(
            StorageFileRecord.id.in_(list(file_ids))
        )
        return {
            record.id: FileFacts(
                file_id=record.id,
                name=record.name,
                kind=kind_of(record.name),
                content_type=record.content_type,
                size_bytes=record.size_bytes,
                leo_readable=leo_readable(record.name, record.size_bytes),
                owner_id=record.user_id,
                org_id=record.org_id,
            )
            for record in await session.scalars(query)
        }

    @asynccontextmanager
    async def open(self, home: Home, viewer: Viewer, file_id: UUID) -> AsyncIterator[ObjectStream]:
        """The bytes of a readable file; `FileUnreadableError` for any other."""
        query = (
            visible_files(self._ports.get(ACCESS_POLICY), viewer)
            .where(StorageFileRecord.id == file_id)
            .with_only_columns(StorageFileRecord.object_key)
        )
        scope = TenancyScope(home, viewer.user_id)
        async with self._transactions.begin(scope, read_only=True) as session:
            key = await session.scalar(query)
        if key is None:
            raise FileUnreadableError
        async with self._objects[home].open(key) as stream:
            yield stream
