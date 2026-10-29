"""`FILE_SOURCES`: a connected drive as knowledge reads it (plan §3.3).

Knowledge keeps its own sources and index; through this port it browses the files the
account lets Shosai see, follows changes since a cursor, and fetches a file's content —
downloaded, or exported as text where the provider keeps its own document formats. A file
too large to fetch whole is `FileTooLargeError`; nothing is streamed past that bound.
"""

from dataclasses import dataclass
from datetime import datetime
from http import HTTPStatus
from typing import Final, Protocol
from uuid import UUID

from shosai.core.kernel.errors import AppError
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.keys import PortKey

# Больше этого файл целиком не забирается: знания индексируют документы, а не архивы.
MAX_CONTENT_BYTES: Final = 50 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class FileEntry:
    """One file or folder."""

    id: str
    name: str
    mime_type: str
    is_folder: bool
    size: int | None = None
    modified_at: datetime | None = None
    parent_ids: tuple[str, ...] = ()
    web_url: str | None = None
    # Версия содержимого: меняется с каждой правкой, по ней знания не перечитывают лишнего.
    version: str | None = None


@dataclass(frozen=True, slots=True)
class FileQuery:
    """A folder's files, or a search by name, a page at a time."""

    folder_id: str | None = None
    text: str | None = None
    page: str | None = None
    limit: int = 100


@dataclass(frozen=True, slots=True)
class FilePage:
    """A page of files and the cursor of the next page."""

    entries: tuple[FileEntry, ...]
    next_page: str | None = None


@dataclass(frozen=True, slots=True)
class FileChanges:
    """Files changed and removed since a cursor; the last page names the next cursor."""

    changed: tuple[FileEntry, ...]
    removed: tuple[str, ...]
    next_page: str | None = None
    cursor: str | None = None


@dataclass(frozen=True, slots=True)
class FileContent:
    """A file's bytes, or its text where it was exported."""

    file_id: str
    name: str
    mime_type: str
    data: bytes


class FileTooLargeError(AppError):
    """The file is larger than Shosai fetches whole."""

    def __init__(self) -> None:
        super().__init__("file_too_large", HTTPStatus.REQUEST_ENTITY_TOO_LARGE)


class FileNotFoundAtProviderError(AppError):
    """No such file, or one the account no longer lets Shosai see."""

    def __init__(self) -> None:
        super().__init__("file_not_found", HTTPStatus.NOT_FOUND)


class FileSourceUnsupportedError(AppError):
    """The connection's app is not a drive Shosai reads."""

    def __init__(self) -> None:
        super().__init__("file_source_unsupported", HTTPStatus.NOT_FOUND)


class FileSources(Protocol):
    """One port for every drive, chosen by the connection's app."""

    async def browse(self, scope: TenancyScope, connection_id: UUID, query: FileQuery) -> FilePage:
        """A page of the files Shosai may see."""
        ...

    async def changes(
        self, scope: TenancyScope, connection_id: UUID, cursor: str | None, page: str | None
    ) -> FileChanges:
        """Changes since the cursor; without one, only the drive's current cursor."""
        ...

    async def content(self, scope: TenancyScope, connection_id: UUID, file_id: str) -> FileContent:
        """A file's content, downloaded or exported as text."""
        ...


FILE_SOURCES: Final = PortKey[FileSources]("connectors.file_sources")
