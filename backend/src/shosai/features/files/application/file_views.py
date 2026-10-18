"""Files and folders as the File Manager shows them (`file-manager/domain/contract.ts`).

A file's Leo use follows its own switch and its folder's; its indexing stage comes from
knowledge's `IndexStatus` port, and a file it has not reported yet is `queued`.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.ports.directory import PortDirectory
from shosai.features.files.contracts import INDEX_STATUS, IndexStage, IndexState
from shosai.features.files.domain.kinds import FileKind, kind_of, leo_readable
from shosai.features.files.domain.leo import LeoVia, leo_use
from shosai.features.files.infrastructure.file_records import FileFolderRecord, StorageFileRecord

QUEUED: Final = IndexState(IndexStage.QUEUED, 0, None, None)


@dataclass(frozen=True, slots=True)
class LeoUseView:
    """How Leo uses a file and how far its indexing got."""

    via: LeoVia
    state: IndexState


@dataclass(frozen=True, slots=True)
class FileView:
    """A file of the File Manager."""

    id: UUID
    name: str
    kind: FileKind
    content_type: str
    size_bytes: int
    folder_id: UUID | None
    modified_at: datetime
    starred: bool
    leo_readable: bool
    leo: LeoUseView | None


@dataclass(frozen=True, slots=True)
class FolderView:
    """A flat folder of the File Manager."""

    id: UUID
    name: str
    updated_at: datetime
    leo: bool


def folder_view(record: FileFolderRecord) -> FolderView:
    """The view of a folder row."""
    return FolderView(record.id, record.name, record.updated_at, record.leo)


async def file_views(
    session: AsyncSession,
    ports: PortDirectory,
    files: Sequence[StorageFileRecord],
    leo_folders: frozenset[UUID],
) -> list[FileView]:
    """The views of file rows, with the indexing stages knowledge reported."""
    states: Mapping[UUID, IndexState] = {}
    for status in ports.all(INDEX_STATUS):
        states = await status.states(session, [record.id for record in files])
    return [file_view(record, leo_folders, states) for record in files]


def file_view(
    record: StorageFileRecord, leo_folders: frozenset[UUID], states: Mapping[UUID, IndexState]
) -> FileView:
    """The view of one file row."""
    readable = leo_readable(record.name, record.size_bytes)
    folder = record.folder_id is not None and record.folder_id in leo_folders
    via = leo_use(readable=readable, own=record.leo_on, folder=folder)
    leo = None if via is None else LeoUseView(via, states.get(record.id, QUEUED))
    return FileView(
        id=record.id, name=record.name, kind=kind_of(record.name),
        content_type=record.content_type, size_bytes=record.size_bytes,
        folder_id=record.folder_id, modified_at=record.modified_at, starred=record.starred,
        leo_readable=readable, leo=leo,
    )  # fmt: skip
