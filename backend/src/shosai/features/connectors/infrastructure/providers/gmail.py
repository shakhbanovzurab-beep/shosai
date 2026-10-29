"""Gmail on the `MAILBOXES` port over `gmail.modify` (API v1, plan step 11, CN-D5).

Every call names its cost in Gmail's quota units, so a burst of reads stays under the
person's quota (the descriptor of "Shosai Mail"); at most four calls of one mailbox run at
once, under Gmail's five. A list gives ids, and the summaries are read with
`format=metadata`. Changes since a cursor are `history.list` from a `historyId`; Gmail keeps
history for about a week and answers 404 for an older one, which the mail slice meets as an
expired cursor and lists again. Without a cursor, the mailbox's current `historyId` is the
cursor. A send is a POST, which the transport never retries: a message goes once.
"""

import asyncio
from collections.abc import Mapping
from http import HTTPStatus
from typing import Any, Final
from urllib.parse import quote

from shosai.features.connectors.contracts.mailboxes import (
    MailboxCursorExpiredError,
    MailChanges,
    MailFolder,
    MailMessage,
    MailNotFoundError,
    MailThread,
    MessageChange,
    MessagePage,
    MessageQuery,
    OutgoingMail,
    SavedDraft,
    SentMail,
)
from shosai.features.connectors.contracts.provider import (
    ProviderBusyError,
    ProviderCall,
    ProviderRefusedError,
    ProviderResponse,
    ProviderSession,
)
from shosai.features.connectors.infrastructure.providers.gmail_shapes import (
    folder_of,
    message_of,
    raw_of,
    summary_of,
)

API: Final = "https://gmail.googleapis.com/gmail/v1/users/me"
# Стоимость методов в единицах квоты Gmail.
COST: Final = {
    "labels": 1, "list": 5, "get": 5, "history": 2, "profile": 1, "thread": 10,
    "modify": 50, "trash": 5, "draft": 10, "send": 100,
}  # fmt: skip
IN_FLIGHT: Final = 4
RATE_REASONS: Final = frozenset({"rateLimitExceeded", "userRateLimitExceeded"})


def _checked(response: ProviderResponse) -> dict[str, Any]:
    status = response.status
    if status == HTTPStatus.NO_CONTENT:
        return {}
    if HTTPStatus.OK <= status < HTTPStatus.MULTIPLE_CHOICES:
        body = response.json()
        if not isinstance(body, dict):
            raise ProviderRefusedError(status, "not_an_object")
        return body
    if status == HTTPStatus.NOT_FOUND:
        raise MailNotFoundError
    body = response.json() if response.body else {}
    error = body.get("error") if isinstance(body, dict) else None
    errors = error.get("errors") if isinstance(error, dict) else None
    reason = errors[0].get("reason") if isinstance(errors, list) and errors else None
    if status == HTTPStatus.FORBIDDEN and reason in RATE_REASONS:
        raise ProviderBusyError(30)
    raise ProviderRefusedError(status, reason if isinstance(reason, str) else None)


class Gmail:
    """The mail adapter of Gmail."""

    async def _call(
        self,
        session: ProviderSession,
        cost: str,
        call: tuple[str, str, str],
        *,
        params: Mapping[str, str] | None = None,
        json_body: object | None = None,
    ) -> dict[str, Any]:
        method, operation, path = call
        return _checked(await session.request(ProviderCall(
            method, operation, f"{API}{path}", params=params, json_body=json_body,
            cost=COST[cost],
        )))  # fmt: skip

    async def folders(self, session: ProviderSession) -> tuple[MailFolder, ...]:
        """Labels as folders."""
        body = await self._call(session, "labels", ("GET", "mail.list_folders", "/labels"))
        labels = body.get("labels", [])
        found = (folder_of(label) for label in labels if isinstance(label, dict))
        return tuple(folder for folder in found if folder is not None)

    async def messages(self, session: ProviderSession, query: MessageQuery) -> MessagePage:
        """A page of ids, read as summaries four at a time."""
        params = {"maxResults": str(query.limit)}
        if query.folder_id:
            params["labelIds"] = query.folder_id
        if query.text:
            params["q"] = query.text
        if query.page:
            params["pageToken"] = query.page
        body = await self._call(
            session, "list", ("GET", "mail.list_messages", "/messages"), params=params
        )
        ids = [str(item["id"]) for item in body.get("messages", []) if isinstance(item, dict)]
        gate = asyncio.Semaphore(IN_FLIGHT)

        async def summary(message_id: str) -> dict[str, Any]:
            async with gate:
                return await self._call(
                    session, "get", ("GET", "mail.read_message", f"/messages/{quote(message_id)}"),
                    params={"format": "metadata"},
                )  # fmt: skip

        found = await asyncio.gather(*(summary(message_id) for message_id in ids))
        return MessagePage(tuple(summary_of(item) for item in found), body.get("nextPageToken"))

    async def changes(
        self, session: ProviderSession, cursor: str | None, page: str | None
    ) -> MailChanges:
        """History since the cursor: messages added or relabelled, messages deleted."""
        if cursor is None:
            profile = await self._call(session, "profile", ("GET", "mail.profile", "/profile"))
            return MailChanges((), (), str(profile.get("historyId")))
        params = {"startHistoryId": cursor} | ({"pageToken": page} if page else {})
        try:
            body = await self._call(
                session, "history", ("GET", "mail.changes", "/history"), params=params
            )
        except MailNotFoundError:
            raise MailboxCursorExpiredError from None
        changed: dict[str, None] = {}
        removed: dict[str, None] = {}
        for record in body.get("history", []):
            for key in ("messagesAdded", "labelsAdded", "labelsRemoved"):
                for entry in record.get(key, []):
                    changed[str(entry["message"]["id"])] = None
            for entry in record.get("messagesDeleted", []):
                removed[str(entry["message"]["id"])] = None
        latest = body.get("historyId")
        next_page = body.get("nextPageToken")
        return MailChanges(
            tuple(key for key in changed if key not in removed), tuple(removed),
            None if next_page else (str(latest) if latest else cursor), next_page,
        )  # fmt: skip

    async def message(self, session: ProviderSession, message_id: str) -> MailMessage:
        """A message in full."""
        body = await self._call(
            session, "get", ("GET", "mail.read_message", f"/messages/{quote(message_id)}"),
            params={"format": "full"},
        )  # fmt: skip
        return message_of(body)

    async def thread(self, session: ProviderSession, thread_id: str) -> MailThread:
        """A conversation in full."""
        body = await self._call(
            session, "thread", ("GET", "mail.read_thread", f"/threads/{quote(thread_id)}"),
            params={"format": "full"},
        )  # fmt: skip
        found = body.get("messages", [])
        messages = tuple(message_of(item) for item in found if isinstance(item, dict))
        return MailThread(str(body.get("id", thread_id)), messages)

    async def change(
        self, session: ProviderSession, ids: tuple[str, ...], change: MessageChange
    ) -> None:
        """Labels and flags of up to a thousand messages in one call."""
        add, remove = list(change.add_folders), list(change.remove_folders)
        if change.read is not None:
            (remove if change.read else add).append("UNREAD")
        if change.starred is not None:
            (add if change.starred else remove).append("STARRED")
        await self._call(
            session, "modify", ("POST", "mail.change_messages", "/messages/batchModify"),
            json_body={"ids": list(ids), "addLabelIds": add, "removeLabelIds": remove},
        )  # fmt: skip

    async def trash(self, session: ProviderSession, ids: tuple[str, ...]) -> None:
        """Each message to the trash."""
        for message_id in ids:
            await self._call(
                session, "trash", ("POST", "mail.trash", f"/messages/{quote(message_id)}/trash")
            )

    async def save_draft(
        self, session: ProviderSession, mail: OutgoingMail, draft_id: str | None
    ) -> SavedDraft:
        """A draft created, or replaced in place."""
        message = {"raw": raw_of(mail)} | ({"threadId": mail.thread_id} if mail.thread_id else {})
        call = ("POST", "mail.save_draft", "/drafts")
        if draft_id is not None:
            call = ("PUT", "mail.save_draft", f"/drafts/{quote(draft_id)}")
        body = await self._call(session, "draft", call, json_body={"message": message})
        saved = body.get("message")
        return SavedDraft(str(body["id"]), saved.get("id") if isinstance(saved, dict) else None)

    async def send(self, session: ProviderSession, mail: OutgoingMail) -> SentMail:
        """The message, once."""
        message = {"raw": raw_of(mail)} | ({"threadId": mail.thread_id} if mail.thread_id else {})
        body = await self._call(
            session, "send", ("POST", "mail.send", "/messages/send"), json_body=message
        )
        return SentMail(str(body["id"]), body.get("threadId"))
