"""Atlassian's endpoints as the connect flow, the refresh and the personal data report meet them.

The double answers with the shapes Atlassian documents: the token endpoint takes JSON and
rotates a single-use refresh token (a reused one is `403 unauthorized_client`), `/me` and
`accessible-resources` name the account and its sites, and `report-accounts` answers 204 or
the verdicts a test sets, refusing the tokens a test names.
"""

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

import httpx
import pytest_asyncio
from cryptography.fernet import Fernet
from prometheus_client import CollectorRegistry
from pydantic import SecretStr
from redis.asyncio import Redis

from shosai.core.config.roles import ProcessRole
from shosai.core.crypto.key_ring import FernetKeyRing
from shosai.core.db.transactions import HomeTransactions
from shosai.core.events.catalog import EventTypes
from shosai.core.events.outbox import EventOutbox
from shosai.core.kv.metrics import KeyValueMetrics
from shosai.core.kv.rate_limits import RateLimiter
from shosai.core.ports.directory import PortDirectory
from shosai.features.connectors.application.atlassian_accounts import (
    AtlassianAccounts,
    ReportTools,
)
from shosai.features.connectors.application.authorize import Authorizer, AuthorizeTools
from shosai.features.connectors.application.callback import CallbackTools, Completer
from shosai.features.connectors.application.grant_tokens import GrantTokens, TokenTools
from shosai.features.connectors.application.installation_audit import InstallationAudit
from shosai.features.connectors.application.offers import Offers
from shosai.features.connectors.channels.http.connect_routes import build_connect_router
from shosai.features.connectors.contracts import CONNECTOR_USES, ConnectorUses
from shosai.features.connectors.contracts.events import CONNECTOR_EVENTS
from shosai.features.connectors.domain.catalogue import App
from shosai.features.connectors.infrastructure.metrics import ConnectorsMetrics
from shosai.features.connectors.infrastructure.oauth.flow_store import FlowStore
from shosai.features.connectors.infrastructure.oauth.tokens import ClientCredentials
from shosai.features.connectors.infrastructure.providers.atlassian import AtlassianAdapter
from shosai.features.connectors.infrastructure.providers.base import (
    ConfiguredClient,
    ProviderRegistry,
)
from shosai.features.identity.contracts import AUTHENTICATOR
from shosai.features.workspaces.contracts import AUDIT_LOG, MEMBERSHIP_READER
from tests.core.web.probe_app import build_probe_app, client_of
from tests.features.billing.people_bench import BearerOfTheTest
from tests.features.connectors.connect_bench import BASE_URL, Workspaces
from tests.harness.database_access import (
    DatabaseAccess,
    ProcessShape,
    open_database_access,
    slot_urls,
)
from tests.harness.run_slot import RunSlot

JIRA_SCOPES = "read:me offline_access read:jira-work write:jira-work manage:jira-webhook"


@dataclass
class AtlassianDouble:
    """auth.atlassian.com and api.atlassian.com as one test sees them."""

    token_requests: list[dict[str, Any]] = field(default_factory=list)
    reports: list[dict[str, Any]] = field(default_factory=list)
    # Чей аккаунт за каким токеном доступа; токены обновления — одноразовые.
    accounts: dict[str, str] = field(default_factory=dict)
    live_refresh: dict[str, str] = field(default_factory=dict)
    issued: int = 0
    emails: dict[str, str] = field(default_factory=dict)
    verdicts: list[dict[str, str]] = field(default_factory=list)
    report_status: int | None = None
    refused_reporters: set[str] = field(default_factory=set)

    def handle(self, request: httpx.Request) -> httpx.Response:
        """One call to Atlassian."""
        url = urlsplit(str(request.url))
        token = request.headers.get("Authorization", "").removeprefix("Bearer ")
        if (url.netloc, url.path) == ("auth.atlassian.com", "/oauth/token"):
            return self.token(json.loads(request.content))
        if url.path == "/me":
            account = self.accounts[token]
            return httpx.Response(200, json={
                "account_type": "atlassian", "account_id": account, "account_status": "active",
                "email": self.emails.get(account, f"{account}@example.com"), "name": account,
                "picture": "https://avatar.test/a.png", "locale": "en-US",
            })  # fmt: skip
        if url.path == "/oauth/token/accessible-resources":
            account = self.accounts[token]
            return httpx.Response(200, json=[{
                "id": f"cloud-{account}", "url": f"https://{account}.atlassian.net",
                "name": account, "scopes": JIRA_SCOPES.split(), "avatarUrl": "https://a.test/s",
            }])  # fmt: skip
        if url.path == "/app/report-accounts/":
            return self.report(token, json.loads(request.content))
        return httpx.Response(404)

    def token(self, body: dict[str, Any]) -> httpx.Response:
        """The token endpoint: a code's first pair, or a refresh that rotates."""
        self.token_requests.append(body)
        if body.get("grant_type") == "refresh_token":
            account = self.live_refresh.pop(body.get("refresh_token", ""), None)
            if account is None:
                return httpx.Response(403, json={
                    "error": "unauthorized_client", "error_description": "refresh_token is invalid",
                })  # fmt: skip
        else:
            account = str(body.get("code", "")).removeprefix("ok:")
        self.issued += 1
        access, refresh = f"acc-{self.issued}", f"ref-{self.issued}"
        self.accounts[access], self.live_refresh[refresh] = account, account
        return httpx.Response(200, json={
            "access_token": access, "refresh_token": refresh, "expires_in": 3600,
            "token_type": "Bearer", "scope": JIRA_SCOPES,
        })  # fmt: skip

    def report(self, token: str, body: dict[str, Any]) -> httpx.Response:
        """The personal data report: refused tokens, a set status, or the set verdicts."""
        self.reports.append({"token": token, **body})
        if token in self.refused_reporters:
            return httpx.Response(401)
        if self.report_status is not None:
            return httpx.Response(self.report_status)
        if not self.verdicts:
            return httpx.Response(204, headers={"Cycle-Period": "604800"})
        return httpx.Response(200, json={"accounts": self.verdicts})


@dataclass(frozen=True, slots=True)
class AtlassianBench:
    """The connect routes, the tokens and the report over the double."""

    http: httpx.AsyncClient
    atlassian: AtlassianDouble
    tokens: GrantTokens
    accounts: AtlassianAccounts
    homes: DatabaseAccess
    # Транзакции воркеров: отчёт обходит дом ролью обхода.
    workers: HomeTransactions
    keys: FernetKeyRing
    counters: CollectorRegistry


@pytest_asyncio.fixture
async def atlassian(
    homes: DatabaseAccess, valkey: Redis, run_slot: RunSlot
) -> AsyncIterator[AtlassianBench]:
    """Jira offered on Atlassian's application, at Shosai's public address."""
    double, workspaces = AtlassianDouble(), Workspaces()
    keys = FernetKeyRing(SecretStr(Fernet.generate_key().decode()))
    ports = PortDirectory()
    ports.install([
        CONNECTOR_USES.bind(ConnectorUses("tests", frozenset({App.JIRA}))),
        MEMBERSHIP_READER.bind(workspaces), AUDIT_LOG.bind(workspaces),
        AUTHENTICATOR.bind(BearerOfTheTest()),
    ])  # fmt: skip
    credentials = ClientCredentials("atlassian-client", SecretStr("atlassian-secret"))
    registry = ProviderRegistry({"atlassian": ConfiguredClient(AtlassianAdapter(), credentials)})
    outbox = EventOutbox(EventTypes(list(CONNECTOR_EVENTS)))
    counters = CollectorRegistry()
    metrics = ConnectorsMetrics(counters)
    flows = FlowStore(valkey)
    tools = AuthorizeTools(Offers(ports, registry), registry, flows, BASE_URL, sealing=True)
    authorizer = Authorizer(homes.transactions, tools)
    limiter = RateLimiter(valkey, KeyValueMetrics(CollectorRegistry()))
    shape = ProcessShape(role=ProcessRole.WORKERS)
    async with (
        httpx.AsyncClient(transport=httpx.MockTransport(double.handle)) as http,
        open_database_access(slot_urls(run_slot), shape) as workers,
    ):
        completer = Completer(
            homes.transactions,
            CallbackTools(flows, registry, http, keys, outbox, InstallationAudit(ports), BASE_URL),
        )
        tokens = GrantTokens(homes.transactions, TokenTools(registry, http, keys, outbox, metrics))
        worker_tokens = GrantTokens(
            workers.transactions, TokenTools(registry, http, keys, outbox, metrics)
        )
        accounts = AtlassianAccounts(
            workers.transactions, ReportTools(worker_tokens, http, outbox, metrics)
        )
        router = build_connect_router((authorizer, completer), ports, limiter)
        app = build_probe_app(extra=(router,)).app
        async with client_of(app, base_url=BASE_URL) as client:
            yield AtlassianBench(
                client, double, tokens, accounts, homes, workers.transactions, keys, counters
            )
