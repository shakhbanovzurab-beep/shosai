"""Gmail's JSON as the `MAILBOXES` port's shapes, and a message as Gmail's `raw` (API v1).

A label is a folder: Gmail's system labels name the inbox, sent, drafts, trash and spam, and
an archived message is one without `INBOX`. A message's headers sit in its `payload`, its
bodies in base64url parts, nested for `multipart/*`; `internalDate` (milliseconds) is when
Gmail received it. A message Shosai writes is RFC 5322, built by the standard library, sent
as base64url.
"""

import base64
from datetime import UTC, datetime
from email.headerregistry import Address
from email.message import EmailMessage
from email.utils import getaddresses
from typing import Any, Final

from shosai.features.connectors.contracts.mailboxes import (
    AttachmentInfo,
    FolderKind,
    MailAddress,
    MailFolder,
    MailMessage,
    MessageSummary,
    OutgoingMail,
)

SYSTEM: Final = {
    "INBOX": FolderKind.INBOX, "SENT": FolderKind.SENT, "DRAFT": FolderKind.DRAFTS,
    "TRASH": FolderKind.TRASH, "SPAM": FolderKind.SPAM,
}  # fmt: skip
# Системные метки, которые не папки: флаги и вкладки входящих.
NOT_FOLDERS: Final = frozenset({"UNREAD", "STARRED", "IMPORTANT", "CHAT"})


def folder_of(label: dict[str, Any]) -> MailFolder | None:
    """A label as a folder; a flag label or an inbox tab is not one."""
    label_id = str(label.get("id", ""))
    if not label_id or label_id in NOT_FOLDERS or label_id.startswith("CATEGORY_"):
        return None
    unread, total = label.get("messagesUnread"), label.get("messagesTotal")
    return MailFolder(
        id=label_id, name=str(label.get("name", label_id)),
        kind=SYSTEM.get(label_id, FolderKind.LABEL),
        unread=unread if isinstance(unread, int) else None,
        total=total if isinstance(total, int) else None,
    )  # fmt: skip


def _headers(payload: dict[str, Any]) -> dict[str, str]:
    found = payload.get("headers")
    pairs = found if isinstance(found, list) else []
    return {
        str(item.get("name", "")).lower(): str(item.get("value", ""))
        for item in pairs
        if isinstance(item, dict)
    }


def addresses(value: str | None) -> tuple[MailAddress, ...]:
    """The addresses of one header."""
    if not value:
        return ()
    return tuple(MailAddress(email, name or None) for name, email in getaddresses([value]) if email)


def _parts(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Every leaf part of a message, depth first."""
    nested = payload.get("parts")
    if not isinstance(nested, list) or not nested:
        return [payload]
    return [leaf for part in nested if isinstance(part, dict) for leaf in _parts(part)]


def _decoded(part: dict[str, Any]) -> str | None:
    body = part.get("body")
    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, str):
        return None
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")


def summary_of(item: dict[str, Any]) -> MessageSummary:
    """A message of `format=metadata` or `full` as a list shows it."""
    payload = item.get("payload")
    payload = payload if isinstance(payload, dict) else {}
    headers = _headers(payload)
    labels = tuple(str(label) for label in item.get("labelIds", []) if isinstance(label, str))
    received = item.get("internalDate")
    senders = addresses(headers.get("from"))
    attached = any(part.get("filename") for part in _parts(payload))
    return MessageSummary(
        id=str(item["id"]), thread_id=item.get("threadId"), folder_ids=labels,
        subject=headers.get("subject", ""), sender=senders[0] if senders else None,
        to=addresses(headers.get("to")), snippet=str(item.get("snippet", "")),
        received_at=datetime.fromtimestamp(int(received) / 1000, UTC)
        if isinstance(received, str) and received.isdigit() else None,
        unread="UNREAD" in labels, starred="STARRED" in labels, has_attachments=attached,
    )  # fmt: skip


def message_of(item: dict[str, Any]) -> MailMessage:
    """A message of `format=full`, opened."""
    payload = item.get("payload")
    payload = payload if isinstance(payload, dict) else {}
    headers = _headers(payload)
    leaves = _parts(payload)
    texts = [
        _decoded(p) for p in leaves if p.get("mimeType") == "text/plain" and not p.get("filename")
    ]
    htmls = [
        _decoded(p) for p in leaves if p.get("mimeType") == "text/html" and not p.get("filename")
    ]
    attachments = tuple(
        AttachmentInfo(
            id=str(part["body"].get("attachmentId", "")), filename=str(part["filename"]),
            mime_type=str(part.get("mimeType", "application/octet-stream")),
            size=int(part["body"].get("size", 0)),
        )
        for part in leaves
        if part.get("filename") and isinstance(part.get("body"), dict)
    )  # fmt: skip
    return MailMessage(
        summary=summary_of(item), cc=addresses(headers.get("cc")),
        body_text=next((text for text in texts if text is not None), None),
        body_html=next((html for html in htmls if html is not None), None),
        attachments=attachments, message_id=headers.get("message-id"),
        in_reply_to=headers.get("in-reply-to"), references=headers.get("references"),
    )  # fmt: skip


def _header_value(people: tuple[MailAddress, ...]) -> list[Address]:
    return [Address(display_name=person.name or "", addr_spec=person.email) for person in people]


def raw_of(mail: OutgoingMail) -> str:
    """The message as Gmail's `raw`: RFC 5322 in base64url."""
    message = EmailMessage()
    message["To"] = _header_value(mail.to)
    if mail.cc:
        message["Cc"] = _header_value(mail.cc)
    if mail.bcc:
        message["Bcc"] = _header_value(mail.bcc)
    message["Subject"] = mail.subject
    if mail.in_reply_to:
        message["In-Reply-To"] = mail.in_reply_to
        message["References"] = mail.references or mail.in_reply_to
    message.set_content(mail.body_text)
    if mail.body_html:
        message.add_alternative(mail.body_html, subtype="html")
    return base64.urlsafe_b64encode(message.as_bytes()).decode().rstrip("=")
