"""Files' handler of a person's data: personal files with their bytes, folders, uploads, usage.

Rows are the person's: files without a workspace, their folders, uploads, usage and the
objects files holds for their personal rows elsewhere (a task's attachments, ADR 0064); a
file handed over to a workspace is the workspace's and stays. Objects are reached only
through their pointers (ADR 0055 point 3): an object is copied by its key, and deleted
only when no row of any owner still names it — a transferred file keeps its key under
the person's prefix, so nothing is ever deleted by prefix. Export gives the rows and the
bytes of every personal file that is not hidden and of every personal held object.
"""

import hashlib
from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import replace
from typing import Final
from uuid import UUID

from sqlalchemy import ColumnElement, Text, and_, bindparam, delete, select, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.account_data.handlers import AccountRef, ExportFile
from shosai.core.account_data.spec import AccountDataSpec, TableCoverage, Treatment
from shosai.core.db.person_rows import (
    PersonRows,
    copy_person_rows,
    person_digest,
    person_lines,
    tables_holding,
    whole_rows,
)
from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.storage.copy import copy_object
from shosai.core.storage.port import MultipartUploads, ObjectStorage
from shosai.features.files.domain.uploads import UploadState
from shosai.features.files.infrastructure import usage_store
from shosai.features.files.infrastructure.file_records import FileFolderRecord, StorageFileRecord
from shosai.features.files.infrastructure.held_records import HeldObjectRecord
from shosai.features.files.infrastructure.upload_records import StorageUsageRecord, UploadRecord

OWNER: Final = "files"
CHUNK_BYTES: Final = 1024 * 1024
KEYS_IN_USE_SQL: Final = text("SELECT files_keys_in_use(:keys)").bindparams(
    bindparam("keys", type_=ARRAY(Text()))
)
MODELS: Final = (
    StorageFileRecord,
    FileFolderRecord,
    UploadRecord,
    StorageUsageRecord,
    HeldObjectRecord,
)
ACCOUNT_DATA: Final = AccountDataSpec(
    OWNER, tuple(TableCoverage(model.__tablename__, Treatment.ERASE) for model in MODELS)
)
TABLES: Final = {
    model.__tablename__: model.metadata.tables[model.__tablename__] for model in MODELS
}
# Переносятся и выгружаются целиком; объектный ключ — не секрет, хеш — свой.
ROWS: Final = (
    whole_rows(TABLES["file_folders"], key="id"),
    whole_rows(TABLES["storage_files"], key="id"),
    whole_rows(TABLES["uploads"], key="id"),
    PersonRows(TABLES["storage_usage"], tuple(TABLES["storage_usage"].columns.keys()), "user_id"),
    replace(whole_rows(TABLES["held_objects"], key="id"), only=lambda _user: personal_held()),
)


def personal_held() -> ColumnElement[bool]:
    """The objects files holds for a person's own rows, not a workspace's."""
    return HeldObjectRecord.org_id.is_(None)


def personal_files(user_id: UUID) -> ColumnElement[bool]:
    """The predicate of the person's own files, not a workspace's."""
    return and_(StorageFileRecord.user_id == user_id, StorageFileRecord.org_id.is_(None))


class FilesAccountData:
    """The `core.account_data_handlers` binding of files."""

    def __init__(
        self,
        transactions: HomeTransactions,
        storage: tuple[Mapping[Home, ObjectStorage], Mapping[Home, MultipartUploads]],
    ) -> None:
        self._transactions = transactions
        self._objects, self._uploads = storage

    @property
    def owner(self) -> str:
        """Files' declaration."""
        return OWNER

    async def export(self, account: AccountRef) -> AsyncIterator[ExportFile]:
        """The rows, then the bytes of each personal file that is not hidden."""
        scope = TenancyScope(account.home, account.user_id)
        for rows in ROWS:
            lines = person_lines(self._transactions, scope, rows, account.user_id)
            yield ExportFile(f"{rows.table.name}.jsonl", lines)
        statement = select(
            StorageFileRecord.id, StorageFileRecord.name, StorageFileRecord.object_key
        )
        statement = statement.where(
            personal_files(account.user_id), StorageFileRecord.deleted_at.is_(None)
        )
        async with self._transactions.begin(scope, read_only=True) as session:
            files = (await session.execute(statement)).all()
        held = select(HeldObjectRecord.id, HeldObjectRecord.filename, HeldObjectRecord.object_key)
        held = held.where(HeldObjectRecord.user_id == account.user_id, personal_held())
        async with self._transactions.begin(scope, read_only=True) as session:
            objects = (await session.execute(held)).all()
        storage = self._objects[account.home]
        for file_id, name, key in files:
            yield ExportFile(f"files/{file_id}/{name}", _object_chunks(storage, key))
        for held_id, name, key in objects:
            yield ExportFile(f"held/{held_id}/{name}", _object_chunks(storage, key))

    async def erase(self, account: AccountRef) -> None:
        """Delete the person's rows, then the objects no other row names."""
        await self.purge(account)

    async def copy(self, account: AccountRef, to_home: Home) -> None:
        """The rows to the other home, then every object they name, under the same key."""
        for rows in ROWS:
            await copy_person_rows(
                self._transactions, rows, account.user_id, (account.home, to_home)
            )
        for key in await self._keys(account):
            await copy_object(self._objects[account.home], self._uploads[to_home], key)

    async def manifest(self, account: AccountRef) -> Mapping[str, str]:
        """A digest of each table, and of every named object's key and size."""
        scope = TenancyScope(account.home, account.user_id)
        digests = {
            rows.table.name: await person_digest(self._transactions, scope, rows, account.user_id)
            for rows in ROWS
        }
        listing = hashlib.sha256()
        storage = self._objects[account.home]
        for key in await self._keys(account):
            info = await storage.head(key)
            listing.update(f"{key}:{None if info is None else info.size}\n".encode())
        digests["objects"] = listing.hexdigest()
        return digests

    async def purge(self, account: AccountRef) -> None:
        """The person's rows in `account.home`, then the objects no remaining row names."""
        keys = await self._keys(account)
        async with self._transactions.begin(TenancyScope(account.home, account.user_id)) as session:
            await usage_store.lock(session, account.user_id)
            await session.execute(delete(StorageFileRecord).where(personal_files(account.user_id)))
            await session.execute(
                delete(HeldObjectRecord).where(
                    HeldObjectRecord.user_id == account.user_id, personal_held()
                )
            )
            for model in (FileFolderRecord, UploadRecord, StorageUsageRecord):
                await session.execute(delete(model).where(model.user_id == account.user_id))
            orphaned = await unnamed(session, keys)
        if orphaned:
            await self._objects[account.home].delete_many(orphaned)

    async def remains(self, account: AccountRef) -> tuple[str, ...]:
        """The tables still holding the person's rows."""
        scope = TenancyScope(account.home, account.user_id)
        tables = [TABLES[name] for name in ("file_folders", "uploads", "storage_usage")]
        found = list(await tables_holding(self._transactions, scope, tables, account.user_id))
        async with self._transactions.begin(scope, read_only=True) as session:
            left = await session.scalar(
                select(StorageFileRecord.id).where(personal_files(account.user_id)).limit(1)
            )
            held = await session.scalar(
                select(HeldObjectRecord.id)
                .where(HeldObjectRecord.user_id == account.user_id, personal_held())
                .limit(1)
            )
        if left is not None:
            found.append("storage_files")
        if held is not None:
            found.append("held_objects")
        return tuple(found)

    async def _keys(self, account: AccountRef) -> list[str]:
        """Every object key the person's files, uploads and held objects name, each once."""
        scope = TenancyScope(account.home, account.user_id)
        files = select(StorageFileRecord.object_key).where(personal_files(account.user_id))
        held = select(HeldObjectRecord.object_key, HeldObjectRecord.preview_key).where(
            HeldObjectRecord.user_id == account.user_id, personal_held()
        )
        uploads = select(UploadRecord.object_key).where(
            UploadRecord.user_id == account.user_id, UploadRecord.state == UploadState.READY.value
        )
        async with self._transactions.begin(scope, read_only=True) as session:
            named = [*(await session.scalars(files)).all(), *(await session.scalars(uploads)).all()]
            for object_key, preview in await session.execute(held):
                named += [key for key in (object_key, preview) if key is not None]
        return sorted(set(named))


async def unnamed(session: AsyncSession, keys: Sequence[str]) -> list[str]:
    """The keys among `keys` that no file row of any owner names any more.

    Row-level security would hide a workspace's rows from the person; `files_keys_in_use`
    answers for every row and returns keys only.
    """
    if not keys:
        return []
    named = await session.scalars(KEYS_IN_USE_SQL, {"keys": list(keys)})
    still = set(named.all())
    return [key for key in keys if key not in still]


async def _object_chunks(storage: ObjectStorage, key: str) -> AsyncIterator[bytes]:
    async with storage.open(key) as stream:
        async for chunk in stream.chunks(CHUNK_BYTES):
            yield chunk
