"""Finishing a connect flow at the provider's callback (connectors plan §3.4).

The flow is taken once by its state and must have started in this browser (the binder
cookie). A refusal on the consent screen is `denied`; a provider's own error maps through its
adapter. The code is exchanged outside any transaction, the granted scopes must cover the
app's, and the account is read; then one transaction writes the grant, its secrets and the
app on it with the events — and, for a workspace's installation, the audit row. Every way out
is a relative redirect to the cabinet with a code, never JSON and never a provider's text.
"""

import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final
from uuid import UUID

import httpx
import structlog

from shosai.core.crypto.key_ring import FernetKeyRing
from shosai.core.db.transactions import HomeTransactions
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.connectors.application.installation_audit import InstallationAudit
from shosai.features.connectors.contracts.events import (
    ConnectionConnected,
    ConnectionRevoked,
    RevokeReason,
)
from shosai.features.connectors.domain.catalogue import AuthKind, Owner, Provider, spec_of
from shosai.features.connectors.domain.flows import (
    FlowError,
    Outcome,
    ReturnKind,
    ReturnTarget,
    binder_matches,
    callback_location,
)
from shosai.features.connectors.domain.refresh import keepalive_at
from shosai.features.connectors.domain.scopes import missing_scopes
from shosai.features.connectors.infrastructure.oauth.flow_store import (
    FlowRecord,
    FlowStore,
    FlowStoreUnavailableError,
)
from shosai.features.connectors.infrastructure.oauth.tokens import (
    TokenEndpoint,
    TokenEndpointError,
    TokenSet,
)
from shosai.features.connectors.infrastructure.oauth.urls import callback_uri
from shosai.features.connectors.infrastructure.providers.base import (
    ACCESS_DENIED,
    AccountIdentity,
    ConfiguredClient,
    ProviderAnswerError,
    ProviderRegistry,
)
from shosai.features.connectors.infrastructure.store.grant_writes import (
    GrantDraft,
    SealedSecrets,
    attach,
    upsert_grant,
)

log = structlog.stdlib.get_logger(__name__)
POPUP: Final = ReturnTarget(ReturnKind.POPUP)


@dataclass(frozen=True, slots=True)
class ProviderAnswer:
    """What the provider's redirect carried."""

    state: str | None
    code: str | None
    error: str | None
    error_description: str | None


@dataclass(frozen=True, slots=True)
class CallbackTools:
    """What finishing a flow uses besides the database."""

    flows: FlowStore
    registry: ProviderRegistry
    http: httpx.AsyncClient
    keys: FernetKeyRing | None
    outbox: EventOutbox
    audit: InstallationAudit
    base_url: str


class FlowFailedError(Exception):
    """A flow ended in error; the code goes to the cabinet."""

    def __init__(self, error: FlowError) -> None:
        super().__init__(error.value)
        self.error = error


class Completer:
    """Finishes connect flows; every outcome is a relative `Location`."""

    def __init__(
        self,
        transactions: HomeTransactions,
        tools: CallbackTools,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._tools = tools
        self._clock = clock

    async def complete(self, provider: Provider, answer: ProviderAnswer, binder: str | None) -> str:
        """Where the browser goes after the provider."""
        flow = await self._flow(provider, answer.state, binder)
        if flow is None:
            return callback_location(
                POPUP, None, Outcome.ERROR, error=FlowError.AUTHORIZATION_EXPIRED
            )
        app = flow.app.value
        try:
            client = self._client(flow)
            if answer.error is not None:
                return self._refused(flow, client, answer)
            if answer.code is None:
                raise FlowFailedError(FlowError.AUTHORIZATION_EXPIRED)
            connection_id = await self._connect(flow, client, answer.code)
        except FlowFailedError as failure:
            log.info("Подключение не состоялось", app=app, reason=failure.error.value)
            return callback_location(flow.target, app, Outcome.ERROR, error=failure.error)
        return callback_location(
            flow.target, app, Outcome.CONNECTED, connection_id=str(connection_id)
        )

    async def _flow(
        self, provider: Provider, state: str | None, binder: str | None
    ) -> FlowRecord | None:
        if state is None:
            return None
        try:
            flow = await self._tools.flows.take(state)
        except FlowStoreUnavailableError:
            log.warning("Поток подключения не прочитан: Valkey недоступен")
            return None
        if flow is None or spec_of(flow.app).provider is not provider:
            return None
        if not binder_matches(flow.binder_digest, binder):
            # Поток начат в другом браузере: аккаунт провайдера не привязывается к чужому Shosai.
            log.warning("Колбэк пришёл не из браузера, начавшего подключение", app=flow.app.value)
            return None
        return flow

    def _client(self, flow: FlowRecord) -> ConfiguredClient:
        client = self._tools.registry.client(flow.client_key)
        if client is None or self._tools.keys is None:
            raise FlowFailedError(FlowError.PROVIDER_UNAVAILABLE)
        return client

    @staticmethod
    def _refused(flow: FlowRecord, client: ConfiguredClient, answer: ProviderAnswer) -> str:
        error = answer.error or ""
        mapped = client.adapter.callback_error(error, answer.error_description)
        if mapped is None and error == ACCESS_DENIED:
            return callback_location(flow.target, flow.app.value, Outcome.DENIED)
        failed = mapped or FlowError.PROVIDER_UNAVAILABLE
        return callback_location(flow.target, flow.app.value, Outcome.ERROR, error=failed)

    async def _connect(self, flow: FlowRecord, client: ConfiguredClient, code: str) -> UUID:
        descriptor = client.adapter.descriptor
        endpoint = TokenEndpoint(self._tools.http, descriptor, client.credentials)
        redirect = callback_uri(self._tools.base_url, descriptor)
        now = self._clock()
        try:
            payload = await endpoint.exchange(code, redirect, flow.verifier)
            tokens = client.adapter.tokens(payload, now)
            identity = await client.adapter.identify(self._tools.http, tokens)
        except (TokenEndpointError, ProviderAnswerError, httpx.HTTPError) as error:
            log.warning("Провайдер не выдал грант", app=flow.app.value, error=type(error).__name__)
            raise FlowFailedError(FlowError.PROVIDER_UNAVAILABLE) from None
        granted = tokens.scopes if tokens.scopes is not None else flow.scopes
        if missing_scopes(spec_of(flow.app), flow.owner, granted):
            raise FlowFailedError(FlowError.SCOPE_MISSING)
        return await self._store(flow, descriptor.idle_expiry, (tokens, identity, granted), now)

    async def _store(
        self,
        flow: FlowRecord,
        idle_expiry: timedelta | None,
        learned: tuple[TokenSet, AccountIdentity, frozenset[str]],
        now: datetime,
    ) -> UUID:
        tokens, identity, granted = learned
        sealed = self._seal(tokens, idle_expiry, now)
        spec = spec_of(flow.app)
        draft = GrantDraft(
            user_id=flow.user_id, org_id=flow.org_id, provider=spec.provider,
            client_key=flow.client_key, auth_kind=AuthKind.OAUTH2,
            external_account_id=identity.external_account_id, account_label=identity.label,
            scopes=granted, meta=identity.meta,
        )  # fmt: skip
        scope = TenancyScope(flow.home, flow.user_id, flow.org_id)
        membership: UUID | None = None
        async with self._transactions.begin(scope) as session:
            if flow.owner is Owner.WORKSPACE and flow.org_id is not None:
                membership = await self._tools.audit.admin_membership(
                    session, flow.org_id, flow.user_id
                )
                if membership is None:
                    raise FlowFailedError(FlowError.NOT_OFFERED)
            grant_id = await upsert_grant(session, draft, sealed)
            attached = await attach(
                session, user_id=flow.user_id, org_id=flow.org_id, app=flow.app, grant_id=grant_id
            )
            events: list[ConnectionConnected | ConnectionRevoked] = []
            if attached.replaced is not None:
                events.append(ConnectionRevoked(
                    connection_id=attached.replaced, user_id=flow.user_id, org_id=flow.org_id,
                    app=flow.app, reason=RevokeReason.REPLACED,
                ))  # fmt: skip
            events.append(ConnectionConnected(
                connection_id=attached.connection_id, user_id=flow.user_id, org_id=flow.org_id,
                app=flow.app, reconnected=attached.reconnected,
            ))  # fmt: skip
            await self._tools.outbox.add_all(session, events)
            if flow.owner is Owner.WORKSPACE and flow.org_id is not None:
                await self._tools.audit.installed(
                    session, flow.org_id, (membership, attached.connection_id, flow.app)
                )
        log.info("Приложение подключено", app=flow.app.value, reconnected=attached.reconnected)
        return attached.connection_id

    def _seal(
        self, tokens: TokenSet, idle_expiry: timedelta | None, now: datetime
    ) -> SealedSecrets:
        keys = self._tools.keys
        if keys is None:
            raise FlowFailedError(FlowError.PROVIDER_UNAVAILABLE)
        refresh = tokens.refresh_token
        spread = secrets.SystemRandom().uniform(-1.0, 1.0)
        return SealedSecrets(
            access_token_enc=keys.encrypt(tokens.access_token.get_secret_value()),
            refresh_token_enc=None if refresh is None else keys.encrypt(refresh.get_secret_value()),
            secret_enc=None, expires_at=tokens.expires_at,
            keepalive_at=None if refresh is None else keepalive_at(now, idle_expiry, spread),
        )  # fmt: skip
