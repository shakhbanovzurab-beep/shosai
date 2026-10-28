"""Connecting an app by a secret the person gives: an app password, an API key, a hook URL.

The secret is probed before it is kept — an IMAP login, a CalDAV `PROPFIND`, Affinity's
whoami, a hook on Zapier's host — by the app's probe, which each provider's step brings; an
app without one is not offered this way. A probed secret is encrypted under core's key ring
and written like any grant, with the same events; a refused one is `credentials_rejected`.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from http import HTTPStatus
from typing import Protocol

import httpx
import structlog
from pydantic import SecretStr

from shosai.core.crypto.key_ring import FernetKeyRing
from shosai.core.db.transactions import HomeTransactions
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.connectors.application.authorize import (
    ConnectUnavailableError,
    NotOfferedError,
)
from shosai.features.connectors.application.offers import Offers
from shosai.features.connectors.contracts import ConnectionView
from shosai.features.connectors.contracts.events import (
    ConnectionConnected,
    ConnectionRevoked,
    RevokeReason,
)
from shosai.features.connectors.domain.catalogue import App, AuthKind, spec_of
from shosai.features.connectors.infrastructure.providers.base import AccountIdentity
from shosai.features.connectors.infrastructure.store.connection_reads import binding
from shosai.features.connectors.infrastructure.store.grant_writes import (
    GrantDraft,
    SealedSecrets,
    attach,
    upsert_grant,
)

log = structlog.stdlib.get_logger(__name__)


class CredentialsRejectedError(AppError):
    """The provider did not accept the secret."""

    def __init__(self) -> None:
        super().__init__("credentials_rejected", HTTPStatus.UNPROCESSABLE_ENTITY)


@dataclass(frozen=True, slots=True)
class GivenSecret:
    """What the person typed: the secret, and the login and the address where needed."""

    secret: SecretStr
    login: str | None = None
    address: str | None = None


class CredentialProbe(Protocol):
    """An app's check of a given secret; `CredentialsRejectedError` when it is refused."""

    @property
    def auth_kind(self) -> AuthKind:
        """Which kind of secret this probe checks."""
        ...

    async def probe(self, http: httpx.AsyncClient, given: GivenSecret) -> AccountIdentity:
        """The account the secret opens."""
        ...


@dataclass(frozen=True, slots=True)
class CredentialTools:
    """What connecting by a secret uses besides the database."""

    offers: Offers
    probes: Mapping[App, CredentialProbe]
    http: httpx.AsyncClient
    keys: FernetKeyRing | None
    outbox: EventOutbox


class Credentials:
    """Connects apps by given secrets."""

    def __init__(self, transactions: HomeTransactions, tools: CredentialTools) -> None:
        self._transactions = transactions
        self._tools = tools

    async def connect(self, scope: TenancyScope, app: App, given: GivenSecret) -> ConnectionView:
        """Probe, keep and attach the secret; the app's connection as it stands now."""
        probe = self._tools.probes.get(app)
        spec = spec_of(app)
        if (
            scope.user_id is None
            or probe is None
            or app not in self._tools.offers.offered()
            or probe.auth_kind not in spec.auth
        ):
            raise NotOfferedError
        keys = self._tools.keys
        if keys is None:
            raise ConnectUnavailableError
        identity = await probe.probe(self._tools.http, given)
        draft = GrantDraft(
            user_id=scope.user_id, org_id=None, provider=spec.provider, client_key=spec.client_key,
            auth_kind=probe.auth_kind, external_account_id=identity.external_account_id,
            account_label=identity.label, scopes=frozenset(), meta=identity.meta,
        )  # fmt: skip
        sealed = SealedSecrets(
            None, None, keys.encrypt(given.secret.get_secret_value()), None, None
        )
        async with self._transactions.begin(scope) as session:
            grant_id = await upsert_grant(session, draft, sealed)
            attached = await attach(
                session, user_id=scope.user_id, org_id=None, app=app, grant_id=grant_id
            )
            events: list[ConnectionConnected | ConnectionRevoked] = []
            if attached.replaced is not None:
                events.append(ConnectionRevoked(
                    connection_id=attached.replaced, user_id=scope.user_id, app=app,
                    reason=RevokeReason.REPLACED,
                ))  # fmt: skip
            events.append(ConnectionConnected(
                connection_id=attached.connection_id, user_id=scope.user_id, app=app,
                reconnected=attached.reconnected,
            ))  # fmt: skip
            await self._tools.outbox.add_all(session, events)
            found = await binding(session, attached.connection_id)
        if found is None:
            message = "только что записанное подключение не читается"
            raise RuntimeError(message)
        log.info("Приложение подключено по секрету", app=app.value)
        return found.view
