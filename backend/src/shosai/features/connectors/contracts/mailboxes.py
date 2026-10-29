"""`MAILBOXES`: a connected mailbox as the mail slice reads and acts in it (plan §3.3).

The mail slice keeps its own index and insights; through this port it lists folders and
labels, lists messages a page at a time, follows changes since a cursor (a cursor the
provider forgot is `MailboxCursorExpiredError`, and the slice lists again), reads a message
or a thread when it is opened, changes flags and folders, moves to trash, saves drafts and
sends. A send is never retried by the transport: the mail slice sends once, through the
Action Gateway. Every call goes through the person's provider session.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from http import HTTPStatus
from typing import Final, Protocol
from uuid import UUID

from shosai.core.kernel.errors import AppError
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.keys import PortKey


class FolderKind(StrEnum):
    """What a folder or label is for."""

    INBOX = "inbox"
    SENT = "sent"
    DRAFTS = "drafts"
    TRASH = "trash"
    SPAM = "spam"
    ARCHIVE = "archive"
    LABEL = "label"


@dataclass(frozen=True, slots=True)
class MailFolder:
    """A folder (IMAP, Outlook) or a label (Gmail)."""

    id: str
    name: str
    kind: FolderKind
    unread: int | None = None
    total: int | None = None


@dataclass(frozen=True, slots=True)
class MailAddress:
    """One address with its display name."""

    email: str
    name: str | None = None


@dataclass(frozen=True, slots=True)
class AttachmentInfo:
    """An attachment named in a message; its bytes are fetched apart."""

    id: str
    filename: str
    mime_type: str
    size: int


@dataclass(frozen=True, slots=True)
class MessageSummary:
    """A message as a list shows it."""

    id: str
    thread_id: str | None
    folder_ids: tuple[str, ...]
    subject: str
    sender: MailAddress | None
    to: tuple[MailAddress, ...]
    snippet: str
    received_at: datetime | None
    unread: bool
    starred: bool
    has_attachments: bool


@dataclass(frozen=True, slots=True)
class MailMessage:
    """A message opened: its summary, the rest of its addressees, its bodies and attachments."""

    summary: MessageSummary
    cc: tuple[MailAddress, ...] = ()
    body_text: str | None = None
    body_html: str | None = None
    attachments: tuple[AttachmentInfo, ...] = ()
    # Заголовки цепочки: Message-ID, на что ответ, вся цепочка.
    message_id: str | None = None
    in_reply_to: str | None = None
    references: str | None = None


@dataclass(frozen=True, slots=True)
class MailThread:
    """A conversation, oldest message first."""

    id: str
    messages: tuple[MailMessage, ...]


@dataclass(frozen=True, slots=True)
class MessageQuery:
    """A page of a folder, or of a search in the provider's own syntax."""

    folder_id: str | None = None
    text: str | None = None
    page: str | None = None
    limit: int = 50


@dataclass(frozen=True, slots=True)
class MessagePage:
    """A page of summaries and the cursor of the next page."""

    messages: tuple[MessageSummary, ...]
    next_page: str | None = None


@dataclass(frozen=True, slots=True)
class MailChanges:
    """What changed since a cursor: messages to read again, messages gone, and the cursors."""

    changed: tuple[str, ...]
    removed: tuple[str, ...]
    cursor: str | None
    next_page: str | None = None


@dataclass(frozen=True, slots=True)
class MessageChange:
    """Folders and flags to change; None leaves a flag as it is."""

    add_folders: tuple[str, ...] = ()
    remove_folders: tuple[str, ...] = ()
    read: bool | None = None
    starred: bool | None = None


@dataclass(frozen=True, slots=True)
class OutgoingMail:
    """A message Shosai writes for the person: new, or a reply in a thread."""

    to: tuple[MailAddress, ...]
    subject: str
    body_text: str
    body_html: str | None = None
    cc: tuple[MailAddress, ...] = ()
    bcc: tuple[MailAddress, ...] = ()
    thread_id: str | None = None
    in_reply_to: str | None = None
    references: str | None = None


@dataclass(frozen=True, slots=True)
class SavedDraft:
    """A draft at the provider."""

    id: str
    message_id: str | None


@dataclass(frozen=True, slots=True)
class SentMail:
    """A sent message at the provider."""

    id: str
    thread_id: str | None


class MailboxCursorExpiredError(AppError):
    """The provider no longer keeps changes since the cursor: the mailbox is listed again."""

    def __init__(self) -> None:
        super().__init__("mailbox_cursor_expired", HTTPStatus.GONE)


class MailNotFoundError(AppError):
    """No such message, thread or draft in the mailbox."""

    def __init__(self) -> None:
        super().__init__("mail_not_found", HTTPStatus.NOT_FOUND)


class MailboxUnsupportedError(AppError):
    """The connection's app is not a mailbox Shosai reads."""

    def __init__(self) -> None:
        super().__init__("mailbox_unsupported", HTTPStatus.NOT_FOUND)


class Mailboxes(Protocol):
    """One port for every mail provider, chosen by the connection's app."""

    async def folders(self, scope: TenancyScope, connection_id: UUID) -> tuple[MailFolder, ...]:
        """The mailbox's folders or labels."""
        ...

    async def messages(
        self, scope: TenancyScope, connection_id: UUID, query: MessageQuery
    ) -> MessagePage:
        """A page of summaries."""
        ...

    async def changes(
        self, scope: TenancyScope, connection_id: UUID, cursor: str | None, page: str | None
    ) -> MailChanges:
        """Changes since the cursor; without one, only the mailbox's current cursor."""
        ...

    async def message(
        self, scope: TenancyScope, connection_id: UUID, message_id: str
    ) -> MailMessage:
        """A message, opened."""
        ...

    async def thread(self, scope: TenancyScope, connection_id: UUID, thread_id: str) -> MailThread:
        """A conversation, opened."""
        ...

    async def change(
        self, scope: TenancyScope, connection_id: UUID, ids: tuple[str, ...], change: MessageChange
    ) -> None:
        """Change folders and flags of messages; archiving removes the inbox."""
        ...

    async def trash(self, scope: TenancyScope, connection_id: UUID, ids: tuple[str, ...]) -> None:
        """Move messages to the trash; nothing is deleted for good."""
        ...

    async def save_draft(
        self, scope: TenancyScope, connection_id: UUID, mail: OutgoingMail, draft_id: str | None
    ) -> SavedDraft:
        """Create a draft, or replace one."""
        ...

    async def send(self, scope: TenancyScope, connection_id: UUID, mail: OutgoingMail) -> SentMail:
        """Send a message once."""
        ...


MAILBOXES: Final = PortKey[Mailboxes]("connectors.mailboxes")
