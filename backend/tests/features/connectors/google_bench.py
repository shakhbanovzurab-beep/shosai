"""Google's two applications as the connect flow, the cabinet and revocation meet them.

The double keeps what each account granted each application, as Google does with
`include_granted_scopes`: a consent adds the asked scopes to the granted ones, less the boxes
the test unticks, and the answer names them all, `email` as `userinfo.email`. A test may hold
back the refresh token of the next answer; revocation records the token it was sent.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import timedelta
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

import httpx
import pytest_asyncio
from cryptography.fernet import Fernet
from prometheus_client import CollectorRegistry
from pydantic import SecretStr
from redis.asyncio import Redis

from shosai.core.crypto.key_ring import FernetKeyRing
from shosai.core.events.catalog import EventTypes
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.homes import Home
from shosai.core.ports.directory import PortDirectory
from shosai.features.connectors.application.authorize import (
    Authorizer,
    AuthorizeTools,
    ConnectRequest,
)
from shosai.features.connectors.application.cabinet_list import CabinetConnectors
from shosai.features.connectors.application.callback import (
    CallbackTools,
    Completer,
    ProviderAnswer,
)
from shosai.features.connectors.application.disconnect import Disconnector
from shosai.features.connectors.application.installation_audit import InstallationAudit
from shosai.features.connectors.application.offers import GmailAccess, Offers
from shosai.features.connectors.application.revocation import GrantRevoker, RevokeTools
from shosai.features.connectors.contracts import CONNECTOR_USES, ConnectorUses
from shosai.features.connectors.contracts.events import CONNECTOR_EVENTS
from shosai.features.connectors.domain.catalogue import App, Provider
from shosai.features.connectors.domain.flows import ReturnKind, ReturnTarget
from shosai.features.connectors.infrastructure.metrics import ConnectorsMetrics
from shosai.features.connectors.infrastructure.oauth.flow_store import FlowStore
from shosai.features.connectors.infrastructure.oauth.tokens import ClientCredentials
from shosai.features.connectors.infrastructure.providers.base import (
    ConfiguredClient,
    ProviderRegistry,
)
from shosai.features.connectors.infrastructure.providers.google import (
    GOOGLE,
    GOOGLE_MAIL,
    GoogleAdapter,
)
from shosai.features.workspaces.contracts import AUDIT_LOG, MEMBERSHIP_READER
from tests.features.connectors.connect_bench import BASE_URL, Workspaces
from tests.harness.database_access import DatabaseAccess

type Person = tuple[Home, UUID]
EMAIL_SCOPE = "https://www.googleapis.com/auth/userinfo.email"


@dataclass
class GoogleDouble:
    """oauth2.googleapis.com and the userinfo endpoint."""

    granted: dict[tuple[str, str], set[str]] = field(default_factory=dict)
    # Что спросил последний вход и какие галочки человек снимет на экране согласия.
    asked: set[str] = field(default_factory=set)
    unticked: set[str] = field(default_factory=set)
    hold_refresh: bool = False
    issued: int = 0
    accounts: dict[str, str] = field(default_factory=dict)
    revoked: list[str] = field(default_factory=list)

    def handle(self, request: httpx.Request) -> httpx.Response:
        """One call to Google."""
        url = urlsplit(str(request.url))
        if url.path == "/token":
            return self.token(parse_qs(request.content.decode()))
        if url.path == "/revoke":
            self.revoked.append(parse_qs(request.content.decode())["token"][0])
            return httpx.Response(200)
        if url.path == "/v1/userinfo":
            token = request.headers["Authorization"].removeprefix("Bearer ")
            account = self.accounts[token]
            return httpx.Response(200, json={
                "sub": f"sub-{account}", "email": f"{account}@gmail.com", "email_verified": True,
                "name": account, "picture": "https://lh3.test/a.png",
            })  # fmt: skip
        return httpx.Response(404)

    def token(self, form: dict[str, list[str]]) -> httpx.Response:
        """A code's answer with every granted scope; a refresh with a new access token only."""
        client = form["client_id"][0]
        self.issued += 1
        access = f"access-{self.issued}"
        if form["grant_type"] == ["refresh_token"]:
            self.accounts[access] = self.accounts[form["refresh_token"][0]]
            return httpx.Response(200, json={"access_token": access, "expires_in": 3599})
        account = form["code"][0].removeprefix("ok:")
        held = self.granted.setdefault((client, account), set())
        held |= self.asked - self.unticked
        held -= self.unticked
        self.accounts[access] = account
        scopes = sorted(EMAIL_SCOPE if scope == "email" else scope for scope in held)
        body: dict[str, object] = {
            "access_token": access, "expires_in": 3599, "token_type": "Bearer",
            "scope": " ".join(scopes), "id_token": "header.payload.signature",
        }  # fmt: skip
        if not self.hold_refresh:
            refresh = f"refresh-{client}-{self.issued}"
            self.accounts[refresh] = account
            body["refresh_token"] = refresh
        return httpx.Response(200, json=body)


@dataclass(frozen=True, slots=True)
class GoogleBench:
    """The flow's halves, the cabinet's list, disconnect and revocation over the double."""

    authorizer: Authorizer
    completer: Completer
    google: GoogleDouble
    cabinet: CabinetConnectors
    disconnector: Disconnector
    revoker: GrantRevoker
    homes: DatabaseAccess
    keys: FernetKeyRing
    # Для сессий провайдера поверх стенда: приложения и outbox.
    wiring: tuple[ProviderRegistry, EventOutbox]

    async def connect(self, person: Person, app: App, account: str = "anna") -> str:
        """Run the person's consent for the app; the callback's location."""
        home, user_id = person
        handoff = await self.authorizer.begin(
            ConnectRequest(user_id, home, app, ReturnTarget(ReturnKind.POPUP))
        )
        query = parse_qs(urlsplit(handoff.authorize_url).query)
        self.google.asked = set(query["scope"][0].split())
        answer = ProviderAnswer(query["state"][0], f"ok:{account}", None, None)
        return await self.completer.complete(Provider.GOOGLE, answer, handoff.cookie.value)


@pytest_asyncio.fixture
async def google(homes: DatabaseAccess, valkey: Redis) -> AsyncIterator[GoogleBench]:
    """Calendar, Drive and Gmail offered; "Shosai Mail" in Testing."""
    double, workspaces = GoogleDouble(), Workspaces()
    keys = FernetKeyRing(SecretStr(Fernet.generate_key().decode()))
    apps = frozenset({App.GOOGLE_CALENDAR, App.GOOGLE_DRIVE, App.GMAIL})
    ports = PortDirectory()
    ports.install([
        CONNECTOR_USES.bind(ConnectorUses("tests", apps)), MEMBERSHIP_READER.bind(workspaces),
        AUDIT_LOG.bind(workspaces),
    ])  # fmt: skip
    registry = ProviderRegistry({
        "google": ConfiguredClient(
            GoogleAdapter(GOOGLE), ClientCredentials("main-client", SecretStr("main-secret"))
        ),
        "google_mail": ConfiguredClient(
            GoogleAdapter(GOOGLE_MAIL), ClientCredentials("mail-client", SecretStr("mail-secret")),
            consent_lifetime=timedelta(days=7),
        ),
    })  # fmt: skip
    outbox = EventOutbox(EventTypes(list(CONNECTOR_EVENTS)))
    metrics = ConnectorsMetrics(CollectorRegistry())
    flows, offers = FlowStore(valkey), Offers(ports, registry, GmailAccess(public=True))
    authorizer = Authorizer(
        homes.transactions, AuthorizeTools(offers, registry, flows, BASE_URL, sealing=True)
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(double.handle)) as http:
        completer = Completer(
            homes.transactions,
            CallbackTools(flows, registry, http, keys, outbox, InstallationAudit(ports), BASE_URL),
        )
        yield GoogleBench(
            authorizer, completer, double, CabinetConnectors(homes.transactions, offers, registry),
            Disconnector(homes.transactions, outbox, registry),
            GrantRevoker(homes.transactions, RevokeTools(registry, http, keys, metrics)),
            homes, keys, (registry, outbox),
        )  # fmt: skip
