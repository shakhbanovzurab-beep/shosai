"""The `MAILBOXES` binding: each call through the connection's provider session, to the mail
adapter of the connection's app (plan §3.3). Gmail comes with step 11, Outlook with step 14,
IMAP (Yandex, Mail.ru) with steps 15 and 18."""

from collections.abc import Mapping
from typing import Protocol
from uuid import UUID

from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.connectors.application.capability_sessions import CapabilitySessions
from shosai.features.connectors.application.provider_access import ConnectorProviderAccess
from shosai.features.connectors.contracts.mailboxes import (
    MailboxUnsupportedError,
    MailChanges,
    MailFolder,
    MailMessage,
    MailThread,
    MessageChange,
    MessagePage,
    MessageQuery,
    OutgoingMail,
    SavedDraft,
    SentMail,
)
from shosai.features.connectors.contracts.provider import ProviderSession
from shosai.features.connectors.domain.catalogue import App


class MailAdapter(Protocol):
    """One provider's mail API over an authorized session."""

    async def folders(self, session: ProviderSession) -> tuple[MailFolder, ...]:
        """Folders or labels."""
        ...

    async def messages(self, session: ProviderSession, query: MessageQuery) -> MessagePage:
        """A page of summaries."""
        ...

    async def changes(
        self, session: ProviderSession, cursor: str | None, page: str | None
    ) -> MailChanges:
        """Changes since a cursor."""
        ...

    async def message(self, session: ProviderSession, message_id: str) -> MailMessage:
        """One message, opened."""
        ...

    async def thread(self, session: ProviderSession, thread_id: str) -> MailThread:
        """One conversation, opened."""
        ...

    async def change(
        self, session: ProviderSession, ids: tuple[str, ...], change: MessageChange
    ) -> None:
        """Folders and flags."""
        ...

    async def trash(self, session: ProviderSession, ids: tuple[str, ...]) -> None:
        """To the trash."""
        ...

    async def save_draft(
        self, session: ProviderSession, mail: OutgoingMail, draft_id: str | None
    ) -> SavedDraft:
        """A draft created or replaced."""
        ...

    async def send(self, session: ProviderSession, mail: OutgoingMail) -> SentMail:
        """A message sent once."""
        ...


class ConnectorMailboxes:
    """Mailboxes of every provider behind one port."""

    def __init__(
        self, access: ConnectorProviderAccess, adapters: Mapping[App, MailAdapter]
    ) -> None:
        self._sessions = CapabilitySessions(access, adapters, MailboxUnsupportedError)

    async def folders(self, scope: TenancyScope, connection_id: UUID) -> tuple[MailFolder, ...]:
        """The mailbox's folders or labels."""
        return await self._sessions.run(scope, connection_id, lambda a, s: a.folders(s))

    async def messages(
        self, scope: TenancyScope, connection_id: UUID, query: MessageQuery
    ) -> MessagePage:
        """A page of summaries."""
        return await self._sessions.run(scope, connection_id, lambda a, s: a.messages(s, query))

    async def changes(
        self, scope: TenancyScope, connection_id: UUID, cursor: str | None, page: str | None
    ) -> MailChanges:
        """Changes since the cursor."""
        return await self._sessions.run(
            scope, connection_id, lambda a, s: a.changes(s, cursor, page)
        )

    async def message(
        self, scope: TenancyScope, connection_id: UUID, message_id: str
    ) -> MailMessage:
        """A message, opened."""
        return await self._sessions.run(scope, connection_id, lambda a, s: a.message(s, message_id))

    async def thread(self, scope: TenancyScope, connection_id: UUID, thread_id: str) -> MailThread:
        """A conversation, opened."""
        return await self._sessions.run(scope, connection_id, lambda a, s: a.thread(s, thread_id))

    async def change(
        self, scope: TenancyScope, connection_id: UUID, ids: tuple[str, ...], change: MessageChange
    ) -> None:
        """Change folders and flags."""
        await self._sessions.run(scope, connection_id, lambda a, s: a.change(s, ids, change))

    async def trash(self, scope: TenancyScope, connection_id: UUID, ids: tuple[str, ...]) -> None:
        """Move messages to the trash."""
        await self._sessions.run(scope, connection_id, lambda a, s: a.trash(s, ids))

    async def save_draft(
        self, scope: TenancyScope, connection_id: UUID, mail: OutgoingMail, draft_id: str | None
    ) -> SavedDraft:
        """Create or replace a draft."""
        return await self._sessions.run(
            scope, connection_id, lambda a, s: a.save_draft(s, mail, draft_id)
        )

    async def send(self, scope: TenancyScope, connection_id: UUID, mail: OutgoingMail) -> SentMail:
        """Send a message once."""
        return await self._sessions.run(scope, connection_id, lambda a, s: a.send(s, mail))
