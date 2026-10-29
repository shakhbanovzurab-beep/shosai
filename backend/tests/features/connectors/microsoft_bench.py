"""Entra and Graph as recorded answers: the connect flow, the tenant, and Outlook Calendar.

The token endpoint answers a code with Graph's scopes by their full address and without
`offline_access`, as Entra does, and an ID token naming the tenant; Graph answers `/me`, the
calendar list, a calendar view's delta in two pages (one item `@removed`), the changes since
`d1`, 410 for a forgotten delta link, and subscriptions created, renewed and stopped.
"""

import base64
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest_asyncio
from cryptography.fernet import Fernet
from opentelemetry.sdk.trace import TracerProvider
from prometheus_client import CollectorRegistry
from pydantic import SecretStr
from redis.asyncio import Redis

from shosai.core.crypto.key_ring import FernetKeyRing
from shosai.core.events.catalog import EventTypes
from shosai.core.events.outbox import EventOutbox
from shosai.core.kv.metrics import KeyValueMetrics
from shosai.core.kv.rate_limits import RateLimiter
from shosai.core.ports.directory import PortDirectory
from shosai.features.connectors.application.authorize import Authorizer, AuthorizeTools
from shosai.features.connectors.application.calendars import ConnectorCalendars
from shosai.features.connectors.application.callback import CallbackTools, Completer
from shosai.features.connectors.application.grant_tokens import GrantTokens, TokenTools
from shosai.features.connectors.application.installation_audit import InstallationAudit
from shosai.features.connectors.application.offers import Offers
from shosai.features.connectors.application.provider_access import ConnectorProviderAccess
from shosai.features.connectors.contracts import CONNECTOR_USES, ConnectorUses
from shosai.features.connectors.contracts.events import CONNECTOR_EVENTS
from shosai.features.connectors.domain.catalogue import App
from shosai.features.connectors.infrastructure.metrics import ConnectorsMetrics
from shosai.features.connectors.infrastructure.oauth.flow_store import FlowStore
from shosai.features.connectors.infrastructure.oauth.tokens import ClientCredentials
from shosai.features.connectors.infrastructure.providers.base import (
    ConfiguredClient,
    ProviderRegistry,
)
from shosai.features.connectors.infrastructure.providers.microsoft import MicrosoftAdapter
from shosai.features.connectors.infrastructure.providers.outlook_calendar import (
    GRAPH,
    OutlookCalendar,
)
from shosai.features.connectors.infrastructure.transport.guards import ProviderGuards
from shosai.features.connectors.infrastructure.transport.session import SessionParts
from shosai.features.workspaces.contracts import AUDIT_LOG, MEMBERSHIP_READER
from tests.features.connectors.connect_bench import BASE_URL, Workspaces
from tests.harness.database_access import DatabaseAccess

DELTA = f"{GRAPH}/me/calendars/cal-1/calendarView/delta"


def id_token(tenant: str) -> str:
    """An unsigned ID token naming its tenant, as the adapter reads it."""
    claims = base64.urlsafe_b64encode(json.dumps({"tid": tenant}).encode()).decode().rstrip("=")
    return f"header.{claims}.signature"


def event(event_id: str, start: str) -> dict[str, Any]:
    """One Graph event in UTC."""
    return {
        "id": event_id, "@odata.etag": f'W/"{event_id}-1"', "subject": "Sync",
        "start": {"dateTime": f"{start}.0000000", "timeZone": "UTC"},
        "end": {"dateTime": f"{start}.0000000", "timeZone": "UTC"}, "isAllDay": False,
        "showAs": "busy", "onlineMeeting": {"joinUrl": "https://teams.microsoft.com/l/m"},
        "organizer": {"emailAddress": {"address": "anna@contoso.com"}},
        "attendees": [{"emailAddress": {"address": "boris@contoso.com", "name": "Boris"},
                       "type": "required", "status": {"response": "tentativelyAccepted"}}],
    }  # fmt: skip


@dataclass
class MicrosoftDouble:
    """login.microsoftonline.com and graph.microsoft.com."""

    calls: list[tuple[str, str, Any]] = field(default_factory=list)
    issued: int = 0

    def handle(self, request: httpx.Request) -> httpx.Response:
        """One call to Entra or Graph."""
        url = urlsplit(str(request.url))
        body = request.content or b""
        self.calls.append((request.method, str(request.url), body))
        if url.netloc == "login.microsoftonline.com":
            self.issued += 1
            return httpx.Response(200, json={
                "token_type": "Bearer", "expires_in": 3599, "id_token": id_token("tenant-1"),
                "access_token": f"ms-acc-{self.issued}", "refresh_token": f"ms-ref-{self.issued}",
                "scope": "https://graph.microsoft.com/calendars.readwrite "
                "https://graph.microsoft.com/User.Read",
            })  # fmt: skip
        path, query = url.path.removeprefix("/v1.0"), parse_qs(url.query)
        if path == "/me":
            return httpx.Response(200, json={"id": "ms-anna", "mail": "anna@contoso.com"})
        if path == "/me/calendars":
            return httpx.Response(200, json={"value": [
                {"id": "cal-1", "name": "Calendar", "canEdit": True, "isDefaultCalendar": True},
            ]})  # fmt: skip
        if path.endswith("/calendarView/delta"):
            return self.delta(query)
        return self.subscriptions(request.method, path)

    def delta(self, query: dict[str, list[str]]) -> httpx.Response:
        """Two pages of a first pass, the changes since `d1`, or a forgotten link."""
        if query.get("$deltatoken") == ["stale"]:
            return httpx.Response(410, json={"error": {"code": "SyncStateNotFound"}})
        if query.get("$deltatoken") == ["d1"]:
            moved = event("ev-2", "2026-11-04T09:00:00")
            return httpx.Response(
                200, json={"value": [moved], "@odata.deltaLink": f"{DELTA}?$deltatoken=d2"}
            )
        if "$skiptoken" in query:
            gone = {"id": "gone-1", "@removed": {"reason": "deleted"}}
            items = [event("ev-2", "2026-11-03T09:00:00"), gone]
            return httpx.Response(
                200, json={"value": items, "@odata.deltaLink": f"{DELTA}?$deltatoken=d1"}
            )
        first = event("ev-1", "2026-11-02T09:00:00")
        return httpx.Response(
            200, json={"value": [first], "@odata.nextLink": f"{DELTA}?$skiptoken=s1"}
        )

    def subscriptions(self, method: str, path: str) -> httpx.Response:
        """A subscription made, renewed, or one Graph no longer knows."""
        if method == "POST" and path == "/subscriptions":
            return httpx.Response(201, json={
                "id": "sub-1", "resource": "me/calendars/cal-1/events",
                "expirationDateTime": "2026-10-31T00:00:00Z",
            })  # fmt: skip
        if method == "PATCH" and path == "/subscriptions/sub-1":
            return httpx.Response(
                200, json={"id": "sub-1", "expirationDateTime": "2026-11-01T00:00:00Z"}
            )
        return httpx.Response(404, json={"error": {"code": "ResourceNotFound"}})


@dataclass(frozen=True, slots=True)
class MicrosoftBench:
    """The connect flow and `CALENDARS` over Entra and Graph."""

    authorizer: Authorizer
    completer: Completer
    calendars: ConnectorCalendars
    api: MicrosoftDouble
    homes: DatabaseAccess
    access: ConnectorProviderAccess


@pytest_asyncio.fixture
async def microsoft(homes: DatabaseAccess, valkey: Redis) -> AsyncIterator[MicrosoftBench]:
    """Outlook Calendar offered on the Entra application."""
    api, workspaces = MicrosoftDouble(), Workspaces()
    keys = FernetKeyRing(SecretStr(Fernet.generate_key().decode()))
    ports = PortDirectory()
    ports.install([
        CONNECTOR_USES.bind(ConnectorUses("calendar", frozenset({App.OUTLOOK_CALENDAR}))),
        MEMBERSHIP_READER.bind(workspaces), AUDIT_LOG.bind(workspaces),
    ])  # fmt: skip
    credentials = ClientCredentials("ms-client", SecretStr("ms-secret"))
    registry = ProviderRegistry({"microsoft": ConfiguredClient(MicrosoftAdapter(), credentials)})
    outbox = EventOutbox(EventTypes(list(CONNECTOR_EVENTS)))
    counters = CollectorRegistry()
    metrics = ConnectorsMetrics(counters)
    flows = FlowStore(valkey)
    tools = AuthorizeTools(Offers(ports, registry), registry, flows, BASE_URL, sealing=True)
    async with httpx.AsyncClient(transport=httpx.MockTransport(api.handle)) as http:
        callback = CallbackTools(
            flows, registry, http, keys, outbox, InstallationAudit(ports), BASE_URL
        )
        tokens = GrantTokens(homes.transactions, TokenTools(registry, http, keys, outbox, metrics))
        guards = ProviderGuards(valkey, RateLimiter(valkey, KeyValueMetrics(counters)))
        parts = SessionParts(tokens, guards, http, metrics, TracerProvider().get_tracer("t"))
        access = ConnectorProviderAccess(homes.transactions, registry, parts)
        yield MicrosoftBench(
            Authorizer(homes.transactions, tools), Completer(homes.transactions, callback),
            ConnectorCalendars(access, {App.OUTLOOK_CALENDAR: OutlookCalendar()}), api, homes,
            access,
        )  # fmt: skip
