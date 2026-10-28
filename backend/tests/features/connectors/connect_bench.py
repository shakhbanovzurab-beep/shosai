"""A connect flow over the slot's homes and Valkey, against a recorded provider double.

The double answers the token endpoint by the code it is given: `ok:<account>` gives tokens
with every scope the flow asked for, `short:<account>` leaves one out, `down` answers 500.
The account's id travels in the token answer, so the adapter's identity read needs no call.
"""

import uuid
from collections.abc import AsyncIterator, Collection, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

import httpx
import pytest_asyncio
from cryptography.fernet import Fernet
from pydantic import SecretStr
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

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
from shosai.features.connectors.application.callback import (
    CallbackTools,
    Completer,
    ProviderAnswer,
)
from shosai.features.connectors.application.installation_audit import InstallationAudit
from shosai.features.connectors.application.offers import Offers
from shosai.features.connectors.contracts import CONNECTOR_USES, ConnectorUses, Handoff
from shosai.features.connectors.contracts.events import CONNECTOR_EVENTS
from shosai.features.connectors.domain.catalogue import App, Provider
from shosai.features.connectors.domain.descriptors import (
    ProviderDescriptor,
    Revocation,
    RevocationKind,
    TokenAuth,
)
from shosai.features.connectors.domain.flows import FlowError, ReturnKind, ReturnTarget
from shosai.features.connectors.infrastructure.oauth.flow_store import FlowStore
from shosai.features.connectors.infrastructure.oauth.tokens import (
    ClientCredentials,
    TokenSet,
    standard_tokens,
)
from shosai.features.connectors.infrastructure.providers.base import (
    AccountIdentity,
    ConfiguredClient,
    HeldTokens,
    ProviderRegistry,
    RevocationFailedError,
)
from shosai.features.identity.contracts import AUTHENTICATOR
from shosai.features.workspaces.contracts import (
    AUDIT_LOG,
    MEMBERSHIP_READER,
    ActiveMembership,
    AuditEntry,
    WorkspaceRole,
)
from tests.features.billing.people_bench import BearerOfTheTest
from tests.harness.database_access import DatabaseAccess

BASE_URL = "https://shosai.test"
GOOGLE = ProviderDescriptor(
    provider=Provider.GOOGLE, client_key="google", authorize_url="https://idp.test/authorize",
    token_url="https://idp.test/token", token_auth=TokenAuth.BODY, pkce=True,
    revocation=Revocation(RevocationKind.REFRESH, "https://idp.test/revoke"),
    authorize_params=(("access_type", "offline"),),
)  # fmt: skip
SLACK = ProviderDescriptor(
    provider=Provider.SLACK, client_key="slack", authorize_url="https://slack.test/authorize",
    token_url="https://slack.test/token", token_auth=TokenAuth.BASIC, pkce=False,
    revocation=Revocation(RevocationKind.ACCESS, "https://slack.test/revoke"),
    scope_separator=",",
)  # fmt: skip
USED = frozenset({App.GOOGLE_CALENDAR, App.GOOGLE_DRIVE, App.SLACK})


@dataclass
class DoubleProvider:
    """The token endpoints of the test providers, recording what they were sent."""

    sent: list[httpx.Request] = field(default_factory=list)
    # Права, которые провайдер «выдал», в его формате: стенд кладёт сюда запрошенные потоком.
    scopes: list[str] = field(default_factory=list)
    separator: str = " "
    # Ответ на обновление: ok, refused (invalid_grant), client (invalid_client), down.
    refresh_mode: str = "ok"
    refreshes: int = 0
    revoked: list[str] = field(default_factory=list)
    # Сколько ближайших отзывов провайдер не подтвердит.
    revoke_failures: int = 0

    def handle(self, request: httpx.Request) -> httpx.Response:
        """Answer a token request by its code."""
        self.sent.append(request)
        form = parse_qs(request.content.decode())
        if form.get("grant_type") == ["refresh_token"]:
            return self.refresh(form["refresh_token"][0])
        code = form.get("code", [""])[0]
        kind, _, account = code.partition(":")
        if kind == "down":
            return httpx.Response(500, json={"error": "server_error"})
        if kind == "refused":
            return httpx.Response(400, json={"error": "invalid_grant"})
        scopes = sorted(self.scopes)
        if kind == "short":
            scopes = scopes[1:]
        body: dict[str, object] = {
            "access_token": f"access-{account}", "refresh_token": f"refresh-{account}",
            "expires_in": 3600, "account": account,
        }  # fmt: skip
        # Многие провайдеры не называют права в ответе: тогда в силе запрошенные потоком.
        if scopes:
            body["scope"] = self.separator.join(scopes)
        return httpx.Response(200, json=body)

    def refresh(self, token: str) -> httpx.Response:
        """Answer a refresh by the mode the test set; a success rotates the refresh token."""
        if self.refresh_mode == "down":
            return httpx.Response(503, json={"error": "temporarily_unavailable"})
        if self.refresh_mode in {"refused", "client"}:
            code = "invalid_grant" if self.refresh_mode == "refused" else "invalid_client"
            return httpx.Response(400 if code == "invalid_grant" else 401, json={"error": code})
        self.refreshes += 1
        round_ = self.refreshes
        body = {
            "access_token": f"access-r{round_}", "refresh_token": f"refresh-r{round_}",
            "expires_in": 3600, "previous": token,
        }  # fmt: skip
        return httpx.Response(200, json=body)


@dataclass(frozen=True, slots=True)
class DoubleAdapter:
    """A provider adapter that reads the account from the token answer."""

    descriptor: ProviderDescriptor
    provider: DoubleProvider

    def tokens(self, payload: Mapping[str, object], now: datetime) -> TokenSet:
        """The standard fields."""
        return standard_tokens(payload, now, self.descriptor.scope_separator)

    async def identify(self, http: httpx.AsyncClient, tokens: TokenSet) -> AccountIdentity:
        """The account the double named."""
        del http
        account = str(tokens.payload["account"])
        return AccountIdentity(account, f"{account}@example.com", {"tenant": "t-1"})

    def callback_error(self, error: str, description: str | None) -> FlowError | None:
        """The double's admin-consent refusal."""
        del description
        return FlowError.ADMIN_CONSENT_REQUIRED if error == "consent_required" else None

    async def revoke(
        self, http: httpx.AsyncClient, credentials: ClientCredentials, tokens: HeldTokens
    ) -> None:
        """Record the revoked refresh token; refuse while the test asks it to."""
        del http, credentials
        if self.provider.revoke_failures > 0:
            self.provider.revoke_failures -= 1
            raise RevocationFailedError
        token = tokens.refresh_token or tokens.access_token
        self.provider.revoked.append("" if token is None else token.get_secret_value())


@dataclass
class Workspaces:
    """Memberships and audit rows as the test sets them."""

    admins: dict[UUID, set[UUID]] = field(default_factory=dict)
    audit: list[AuditEntry] = field(default_factory=list)

    async def active(self, session: AsyncSession, user_id: UUID) -> tuple[ActiveMembership, ...]:
        """The person's memberships: admin where the test said so."""
        del session
        return tuple(
            ActiveMembership(org_id, uuid.uuid5(org_id, str(user_id)), WorkspaceRole.ADMIN)
            for org_id, people in self.admins.items()
            if user_id in people
        )

    async def has_memberships(self, session: AsyncSession, user_id: UUID) -> bool:
        """Whether the person is anyone's admin here."""
        return bool(await self.active(session, user_id))

    async def members(
        self, session: AsyncSession, org_id: UUID, user_ids: Collection[UUID]
    ) -> Mapping[UUID, ActiveMembership]:
        """The admins among the people."""
        del session
        people = self.admins.get(org_id, set())
        return {
            user: ActiveMembership(org_id, uuid.uuid5(org_id, str(user)), WorkspaceRole.ADMIN)
            for user in user_ids
            if user in people
        }

    async def record(self, session: AsyncSession, entry: AuditEntry) -> None:
        """Keep the audit row."""
        del session
        self.audit.append(entry)


@dataclass(frozen=True, slots=True)
class ConnectBench:
    """The flow's two halves and what they write."""

    authorizer: Authorizer
    completer: Completer
    provider: DoubleProvider
    keys: FernetKeyRing
    workspaces: Workspaces
    homes: DatabaseAccess
    ports: PortDirectory
    # Для жизненного цикла гранта: приложения, клиент дубля и outbox.
    wiring: tuple[ProviderRegistry, httpx.AsyncClient, EventOutbox]

    async def start(
        self, person: tuple[Home, UUID], app: App, org_id: UUID | None = None
    ) -> Handoff:
        """Begin a flow of the person's, back to the popup or to chats for a workspace."""
        home, user_id = person
        kind = ReturnKind.POPUP if org_id is None else ReturnKind.CHATS
        request = ConnectRequest(user_id, home, app, ReturnTarget(kind), org_id=org_id)
        return await self.authorizer.begin(request)

    async def finish(
        self,
        handoff: Handoff,
        code: str | None,
        *,
        binder: str | None = None,
        error: str | None = None,
        provider: Provider = Provider.GOOGLE,
    ) -> str:
        """The provider's redirect for a started flow, from the browser that started it."""
        query = parse_qs(urlsplit(handoff.authorize_url).query)
        state = query["state"][0]
        separator = "," if provider is Provider.SLACK else " "
        self.provider.scopes = query.get("scope", [""])[0].split(separator)
        self.provider.separator = separator
        answer = ProviderAnswer(state, code, error, None)
        return await self.completer.complete(provider, answer, binder or handoff.cookie.value)


@pytest_asyncio.fixture
async def connect_bench(homes: DatabaseAccess, valkey: Redis) -> AsyncIterator[ConnectBench]:
    """The connect flow with the double providers of Google and Slack."""
    provider, workspaces = DoubleProvider(), Workspaces()
    keys = FernetKeyRing(SecretStr(Fernet.generate_key().decode()))
    ports = PortDirectory()
    ports.install([
        CONNECTOR_USES.bind(ConnectorUses("tests", USED)), MEMBERSHIP_READER.bind(workspaces),
        AUDIT_LOG.bind(workspaces), AUTHENTICATOR.bind(BearerOfTheTest()),
    ])  # fmt: skip
    credentials = ClientCredentials("client-id", SecretStr("client-secret"))
    registry = ProviderRegistry({
        "google": ConfiguredClient(DoubleAdapter(GOOGLE, provider), credentials),
        "slack": ConfiguredClient(DoubleAdapter(SLACK, provider), credentials),
    })  # fmt: skip
    flows = FlowStore(valkey)
    outbox = EventOutbox(EventTypes(list(CONNECTOR_EVENTS)))
    tools = AuthorizeTools(Offers(ports, registry), registry, flows, BASE_URL, sealing=True)
    authorizer = Authorizer(homes.transactions, tools)
    async with httpx.AsyncClient(transport=httpx.MockTransport(provider.handle)) as http:
        audit = InstallationAudit(ports)
        completer = Completer(
            homes.transactions,
            CallbackTools(flows, registry, http, keys, outbox, audit, BASE_URL),
        )
        yield ConnectBench(
            authorizer, completer, provider, keys, workspaces, homes, ports,
            (registry, http, outbox),
        )  # fmt: skip
