"""Starting a connect flow: for a person's app or a workspace's installation (plan §3.4).

The app must be offered and, for a workspace, installable there. The flow asks for the app's
scopes — with the union of the owner's grant at the same application where the provider keeps
one token per account (Yandex, Atlassian) — and is kept 10 minutes in Valkey under its state,
with the PKCE verifier and the digest of the browser binder that the starting response sets
as an httpOnly cookie. A refusal is a code the cabinet words.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Final
from uuid import UUID

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.connectors.application.offers import Offers
from shosai.features.connectors.contracts import FlowCookie, Handoff
from shosai.features.connectors.domain.catalogue import App, AuthKind, Owner, spec_of
from shosai.features.connectors.domain.descriptors import ProviderDescriptor
from shosai.features.connectors.domain.flows import (
    FLOW_LIFETIME,
    ReturnTarget,
    digest_of,
    new_binder,
    new_nonce,
    new_verifier,
)
from shosai.features.connectors.domain.scopes import requested_scopes
from shosai.features.connectors.infrastructure.oauth.flow_store import (
    FlowRecord,
    FlowStore,
    FlowStoreUnavailableError,
)
from shosai.features.connectors.infrastructure.oauth.urls import (
    AuthorizeQuery,
    authorize_url,
    callback_uri,
)
from shosai.features.connectors.infrastructure.providers.base import ProviderRegistry
from shosai.features.connectors.infrastructure.store.grant_writes import held_scopes

COOKIE_NAME: Final = "shosai_connect"
COOKIE_PATH: Final = "/v1/connectors/oauth"


def cookie_path(descriptor: ProviderDescriptor) -> str:
    """Where the browser sends the binder back: the provider's own callback path, if it has one."""
    return descriptor.redirect_path or COOKIE_PATH


class NotOfferedError(AppError):
    """The app is not offered by this deployment, or not for this owner."""

    def __init__(self) -> None:
        super().__init__("not_offered", HTTPStatus.CONFLICT)


class ConnectUnavailableError(AppError):
    """A connect flow cannot start now: Valkey or the key ring is missing."""

    def __init__(self) -> None:
        super().__init__("connect_unavailable", HTTPStatus.SERVICE_UNAVAILABLE)


@dataclass(frozen=True, slots=True)
class ConnectRequest:
    """Who starts which flow, and where the browser comes back to."""

    user_id: UUID
    home: Home
    app: App
    target: ReturnTarget
    org_id: UUID | None = None
    replaces: UUID | None = None


@dataclass(frozen=True, slots=True)
class AuthorizeTools:
    """What starting a flow reads: offers, applications, Valkey, the public address."""

    offers: Offers
    registry: ProviderRegistry
    flows: FlowStore
    base_url: str
    # Есть ли кольцо ключей Fernet: без него грант нечем зашифровать.
    sealing: bool


class Authorizer:
    """Starts connect flows."""

    def __init__(
        self,
        transactions: HomeTransactions,
        tools: AuthorizeTools,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._tools = tools
        self._clock = clock

    async def begin(self, request: ConnectRequest) -> Handoff:
        """A new flow: the provider's authorize URL and the binder cookie."""
        spec = spec_of(request.app)
        owner = Owner.PERSON if request.org_id is None else Owner.WORKSPACE
        if (
            request.app not in self._tools.offers.offered()
            or owner not in spec.owners
            or spec.auth[0] is not AuthKind.OAUTH2
        ):
            raise NotOfferedError
        client = self._tools.registry.client(spec.client_key)
        if client is None:
            raise NotOfferedError
        if not self._tools.sealing:
            raise ConnectUnavailableError
        descriptor = client.adapter.descriptor
        held: frozenset[str] = frozenset()
        if descriptor.union_scopes:
            scope = TenancyScope(request.home, request.user_id, request.org_id)
            async with self._transactions.begin(scope, read_only=True) as session:
                held = await held_scopes(session, request.user_id, request.org_id, spec.client_key)
        scopes = requested_scopes(spec, owner, held=held, union_required=descriptor.union_scopes)
        nonce, verifier, binder = new_nonce(), new_verifier(), new_binder()
        flow = FlowRecord(
            user_id=request.user_id, home=request.home, org_id=request.org_id, app=request.app,
            client_key=spec.client_key, verifier=verifier, binder_digest=digest_of(binder),
            target=request.target, scopes=scopes, replaces=request.replaces,
        )  # fmt: skip
        try:
            await self._tools.flows.open(nonce, flow)
        except FlowStoreUnavailableError:
            raise ConnectUnavailableError from None
        query = AuthorizeQuery(
            client_id=client.credentials.client_id,
            redirect_uri=callback_uri(self._tools.base_url, descriptor), state=nonce,
            scopes=scopes, verifier=verifier,
        )  # fmt: skip
        url = authorize_url(descriptor, query)
        lifetime = int(FLOW_LIFETIME.total_seconds())
        return Handoff(
            authorize_url=url,
            expires_at=self._clock() + FLOW_LIFETIME,
            cookie=FlowCookie(COOKIE_NAME, binder, cookie_path(descriptor), lifetime),
        )
