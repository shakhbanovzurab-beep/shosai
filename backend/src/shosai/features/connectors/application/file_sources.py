"""The `FILE_SOURCES` binding: each call through the connection's provider session, to the
drive adapter of the connection's app (plan §3.3). Google Drive comes with step 12, Yandex
Disk with step 17, Dropbox with step 23."""

from collections.abc import Mapping
from typing import Protocol
from uuid import UUID

from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.connectors.application.capability_sessions import CapabilitySessions
from shosai.features.connectors.application.provider_access import ConnectorProviderAccess
from shosai.features.connectors.contracts.files import (
    FileChanges,
    FileContent,
    FilePage,
    FileQuery,
    FileSourceUnsupportedError,
)
from shosai.features.connectors.contracts.provider import ProviderSession
from shosai.features.connectors.domain.catalogue import App


class FileAdapter(Protocol):
    """One provider's drive API over an authorized session."""

    async def browse(self, session: ProviderSession, query: FileQuery) -> FilePage:
        """A page of files."""
        ...

    async def changes(
        self, session: ProviderSession, cursor: str | None, page: str | None
    ) -> FileChanges:
        """Changes since a cursor."""
        ...

    async def content(self, session: ProviderSession, file_id: str) -> FileContent:
        """A file's content."""
        ...


class ConnectorFileSources:
    """Drives of every provider behind one port."""

    def __init__(
        self, access: ConnectorProviderAccess, adapters: Mapping[App, FileAdapter]
    ) -> None:
        self._sessions = CapabilitySessions(access, adapters, FileSourceUnsupportedError)

    async def browse(self, scope: TenancyScope, connection_id: UUID, query: FileQuery) -> FilePage:
        """A page of the files Shosai may see."""
        return await self._sessions.run(scope, connection_id, lambda a, s: a.browse(s, query))

    async def changes(
        self, scope: TenancyScope, connection_id: UUID, cursor: str | None, page: str | None
    ) -> FileChanges:
        """Changes since the cursor."""
        return await self._sessions.run(
            scope, connection_id, lambda a, s: a.changes(s, cursor, page)
        )

    async def content(self, scope: TenancyScope, connection_id: UUID, file_id: str) -> FileContent:
        """A file's content."""
        return await self._sessions.run(scope, connection_id, lambda a, s: a.content(s, file_id))
