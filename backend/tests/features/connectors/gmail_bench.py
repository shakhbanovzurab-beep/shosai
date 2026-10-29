"""Gmail's API as recorded answers, behind `MAILBOXES` over a connected "Shosai Mail" grant.

The double answers the shapes Google documents: labels with system flags and inbox tabs, a
list of two messages and their metadata, a full message with plain, HTML and a PDF part, a
history since `100` (added, relabelled, deleted) and 404 for the forgotten `1`, a profile,
drafts and a send that fails once with 503. "Shosai Mail" here has a quota of 30 units a
minute, so a burst is visible.
"""

import base64
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field, replace
from datetime import timedelta
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest_asyncio
from opentelemetry.sdk.trace import TracerProvider
from prometheus_client import CollectorRegistry
from pydantic import SecretStr
from redis.asyncio import Redis

from shosai.core.kv.metrics import KeyValueMetrics
from shosai.core.kv.rate_limits import RateLimiter
from shosai.features.connectors.application.grant_tokens import GrantTokens, TokenTools
from shosai.features.connectors.application.mailboxes import ConnectorMailboxes
from shosai.features.connectors.application.provider_access import ConnectorProviderAccess
from shosai.features.connectors.domain.catalogue import App
from shosai.features.connectors.domain.descriptors import LimitSubject, ProviderLimit
from shosai.features.connectors.infrastructure.metrics import ConnectorsMetrics
from shosai.features.connectors.infrastructure.oauth.tokens import ClientCredentials
from shosai.features.connectors.infrastructure.providers.base import (
    ConfiguredClient,
    ProviderRegistry,
)
from shosai.features.connectors.infrastructure.providers.gmail import Gmail
from shosai.features.connectors.infrastructure.providers.google import GOOGLE_MAIL, GoogleAdapter
from shosai.features.connectors.infrastructure.transport.guards import ProviderGuards
from shosai.features.connectors.infrastructure.transport.session import SessionParts
from tests.features.connectors.google_bench import GoogleBench

QUOTA = 30
LIMITED_MAIL = replace(
    GOOGLE_MAIL,
    limits=(ProviderLimit("units", LimitSubject.ACCOUNT, QUOTA, timedelta(minutes=1), QUOTA),),
)


def b64(text: str) -> str:
    """Gmail's base64url body without padding."""
    return base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")


def message(message_id: str) -> dict[str, Any]:
    """A message of the mailbox in `format=full`."""
    return {
        "id": message_id, "threadId": "t1", "labelIds": ["INBOX", "UNREAD"],
        "snippet": "Hi Anna", "internalDate": "1793232000000",
        "payload": {"mimeType": "multipart/mixed", "headers": [
            {"name": "From", "value": "Boris <boris@example.com>"},
            {"name": "To", "value": "anna@gmail.com"}, {"name": "Subject", "value": "Contract"},
            {"name": "Message-ID", "value": f"<{message_id}@example.com>"},
        ], "parts": [
            {"mimeType": "multipart/alternative", "parts": [
                {"mimeType": "text/plain", "body": {"data": b64("Hi Anna\n")}},
                {"mimeType": "text/html", "body": {"data": b64("<p>Hi Anna</p>")}},
            ]},
            {"mimeType": "application/pdf", "filename": "contract.pdf",
             "body": {"attachmentId": "att-1", "size": 2048}},
        ]},
    }  # fmt: skip


@dataclass
class GmailDouble:
    """gmail.googleapis.com for one mailbox."""

    calls: list[tuple[str, str, dict[str, list[str]], Any]] = field(default_factory=list)
    send_failures: int = 1

    def handle(self, request: httpx.Request) -> httpx.Response:
        """One call to Gmail."""
        url = urlsplit(str(request.url))
        query = parse_qs(url.query)
        body = json.loads(request.content) if request.content else None
        path = url.path.removeprefix("/gmail/v1/users/me")
        self.calls.append((request.method, path, query, body))
        if path == "/labels":
            return httpx.Response(200, json={"labels": [
                {"id": "INBOX", "name": "INBOX", "type": "system", "messagesUnread": 2},
                {"id": "UNREAD", "name": "UNREAD", "type": "system"},
                {"id": "CATEGORY_PERSONAL", "name": "CATEGORY_PERSONAL", "type": "system"},
                {"id": "Label_7", "name": "Clients", "type": "user"},
            ]})  # fmt: skip
        if path == "/messages":
            return httpx.Response(200, json={"messages": [
                {"id": "m1", "threadId": "t1"}, {"id": "m2", "threadId": "t1"},
            ], "nextPageToken": "n2"})  # fmt: skip
        if path.startswith("/messages/m") and request.method == "GET":
            return httpx.Response(200, json=message(path.rsplit("/", 1)[1]))
        return self.history(path, query) if path in {"/history", "/profile"} else self.act(path)

    def history(self, path: str, query: dict[str, list[str]]) -> httpx.Response:
        """The current cursor, the changes since one, or a forgotten one."""
        if path == "/profile":
            return httpx.Response(200, json={"emailAddress": "anna@gmail.com", "historyId": "100"})
        if query["startHistoryId"] == ["1"]:
            return httpx.Response(404, json={"error": {
                "code": 404, "message": "Requested entity was not found.",
                "errors": [{"reason": "notFound"}],
            }})  # fmt: skip
        return httpx.Response(200, json={"historyId": "103", "history": [
            {"id": "101", "messagesAdded": [{"message": {"id": "m3", "threadId": "t2"}}]},
            {"id": "102", "labelsRemoved": [{"message": {"id": "m1"}, "labelIds": ["UNREAD"]}]},
            {"id": "103", "messagesDeleted": [{"message": {"id": "m2"}}]},
        ]})  # fmt: skip

    def act(self, path: str) -> httpx.Response:
        """Labels changed, a draft saved, a message sent — the first send fails."""
        if path == "/messages/batchModify":
            return httpx.Response(204)
        if path.startswith("/drafts"):
            return httpx.Response(
                200, json={"id": "d1", "message": {"id": "dm1", "threadId": "t1"}}
            )
        if path == "/messages/send" and self.send_failures > 0:
            self.send_failures -= 1
            return httpx.Response(503)
        return httpx.Response(200, json={"id": "sent-1", "threadId": "t1", "labelIds": ["SENT"]})


@dataclass(frozen=True, slots=True)
class GmailBench:
    """`MAILBOXES` over a person's connected Gmail."""

    mailboxes: ConnectorMailboxes
    api: GmailDouble
    google: GoogleBench


@pytest_asyncio.fixture
async def gmail(google: GoogleBench, valkey: Redis) -> AsyncIterator[GmailBench]:
    """Gmail behind `MAILBOXES`, with a small quota."""
    api = GmailDouble()
    _registry, outbox = google.wiring
    credentials = ClientCredentials("mail-client", SecretStr("mail-secret"))
    registry = ProviderRegistry(
        {"google_mail": ConfiguredClient(GoogleAdapter(LIMITED_MAIL), credentials)}
    )

    def route(request: httpx.Request) -> httpx.Response:
        if request.url.host == "gmail.googleapis.com":
            return api.handle(request)
        return google.google.handle(request)

    counters = CollectorRegistry()
    metrics = ConnectorsMetrics(counters)
    async with httpx.AsyncClient(transport=httpx.MockTransport(route)) as http:
        tokens = GrantTokens(
            google.homes.transactions, TokenTools(registry, http, google.keys, outbox, metrics)
        )
        guards = ProviderGuards(valkey, RateLimiter(valkey, KeyValueMetrics(counters)))
        parts = SessionParts(tokens, guards, http, metrics, TracerProvider().get_tracer("t"))
        access = ConnectorProviderAccess(google.homes.transactions, registry, parts)
        yield GmailBench(ConnectorMailboxes(access, {App.GMAIL: Gmail()}), api, google)
