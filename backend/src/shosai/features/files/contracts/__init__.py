"""What other slices may use of files (files plan §3.2; ADR 0055).

Every slice that takes bytes goes through files' uploads: the person uploads straight to
their home's bucket, and the slice claims the ready upload by its id (`Uploads`). Files a
person may read come through `FileReader`, which applies workspaces' access policy.
`knowledge` binds `IndexStatus` to report how a file Leo uses is indexed; until it does,
every such file is `queued`. The events are in `contracts.events`.
"""

from collections.abc import Mapping, Sequence
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from enum import StrEnum
from http import HTTPStatus
from typing import Final, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.kernel.errors import AppError
from shosai.core.kernel.homes import Home
from shosai.core.ports.keys import PortKey
from shosai.core.storage.port import ObjectStream
from shosai.features.files.domain.kinds import FileKind
from shosai.features.files.domain.purposes import UploadPurpose
from shosai.features.workspaces.contracts import Viewer

__all__ = [
    "FILE_READER",
    "INDEX_STATUS",
    "UPLOADS",
    "ClaimedObject",
    "FileFacts",
    "FileKind",
    "FileReader",
    "FileUnreadableError",
    "IndexStage",
    "IndexState",
    "IndexStatus",
    "UploadNotClaimableError",
    "UploadPurpose",
    "Uploads",
]


@dataclass(frozen=True, slots=True)
class ClaimedObject:
    """A ready upload the caller now owns: where its bytes are and what they are."""

    upload_id: UUID
    object_key: str
    size_bytes: int
    content_type: str
    filename: str


class UploadNotClaimableError(AppError):
    """The upload is missing, not the caller's, not ready, or for another purpose (409)."""

    def __init__(self) -> None:
        super().__init__("upload_not_claimable", HTTPStatus.CONFLICT)


class Uploads(Protocol):
    """Ready uploads handed to the slice they are for."""

    async def claim(
        self, session: AsyncSession, upload_id: UUID, purpose: UploadPurpose
    ) -> ClaimedObject:
        """Take the session's person's ready upload of that purpose in the caller's transaction.

        A second claim of the same upload answers the same object; anything else raises
        `UploadNotClaimableError`.
        """
        ...


@dataclass(frozen=True, slots=True)
class FileFacts:
    """A file the viewer may read, as other slices see it, with whose it is and where."""

    file_id: UUID
    name: str
    kind: FileKind
    content_type: str
    size_bytes: int
    leo_readable: bool
    # Кто загрузил файл и в каком workspace он лежит; None — личный файл владельца.
    owner_id: UUID | None = None
    org_id: UUID | None = None


class FileUnreadableError(AppError):
    """No such file the viewer may read: missing, deleted, or not theirs to read (404)."""

    def __init__(self) -> None:
        super().__init__("file_not_found", HTTPStatus.NOT_FOUND)


class FileReader(Protocol):
    """Files a viewer may read, through workspaces' access policy (inv-14).

    A deleted file and a file of an account in identity's deletion window are read by
    nobody. Knowledge indexes files and re-checks every search hit through this port.
    """

    async def facts(
        self, session: AsyncSession, viewer: Viewer, file_ids: Sequence[UUID]
    ) -> Mapping[UUID, FileFacts]:
        """The readable ones among `file_ids`; the others are absent."""
        ...

    def open(
        self, home: Home, viewer: Viewer, file_id: UUID
    ) -> AbstractAsyncContextManager[ObjectStream]:
        """The bytes of a readable file; `FileUnreadableError` for any other. The bytes are
        read after the access check's transaction ends."""
        ...


class IndexStage(StrEnum):
    """How far knowledge got with a file Leo uses (the cabinet's `IndexStatus`)."""

    QUEUED = "queued"
    PARSING = "parsing"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    INDEXED = "indexed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class IndexState:
    """A file's indexing: its stage, progress within it, chunks and the failure code."""

    stage: IndexStage
    progress: int
    chunk_count: int | None
    error: str | None


class IndexStatus(Protocol):
    """Indexing states of files, bound by knowledge."""

    async def states(
        self, session: AsyncSession, file_ids: Sequence[UUID]
    ) -> Mapping[UUID, IndexState]:
        """The known states; a file without one is queued."""
        ...


UPLOADS: Final = PortKey[Uploads]("files.uploads")
FILE_READER: Final = PortKey[FileReader]("files.file_reader")
# Привязывает knowledge; пока его нет, порт пуст и все файлы Leo — в очереди.
INDEX_STATUS: Final = PortKey[IndexStatus]("files.index_status")
