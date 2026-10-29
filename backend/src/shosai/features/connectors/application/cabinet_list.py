"""Settings > Connectors: the offered apps and the person's connections, in one read (§3.7).

An app is listed when it is offered or when the person holds a connection of it, so a
connection can always be disconnected. A connected app says whether the provider would still
list Shosai's access after its disconnect: while other apps share its grant, or where the
provider has no revocation for applications. A connection whose application gives consents a
fixed life (a Google project in Testing: seven days) says by when it must be reconnected.
"""

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.connectors.application.offers import Offers
from shosai.features.connectors.contracts import ConnectionView, NotConnectedError
from shosai.features.connectors.domain.catalogue import CATALOGUE, App, AppSpec
from shosai.features.connectors.domain.descriptors import RevocationKind
from shosai.features.connectors.infrastructure.providers.base import ProviderRegistry
from shosai.features.connectors.infrastructure.store.connection_reads import (
    ConnectionBinding,
    bindings,
)
from shosai.features.connectors.infrastructure.store.records import ConnectionRecord


@dataclass(frozen=True, slots=True)
class ConnectorRow:
    """One row of Settings > Connectors."""

    spec: AppSpec
    connection: ConnectionView | None
    access_remains_at_provider: bool
    reconnect_by: datetime | None = None


class CabinetConnectors:
    """The person's view of the catalogue."""

    def __init__(
        self, transactions: HomeTransactions, offers: Offers, registry: ProviderRegistry
    ) -> None:
        self._transactions = transactions
        self._offers = offers
        self._registry = registry

    async def rows(self, scope: TenancyScope) -> list[ConnectorRow]:
        """The rows in the catalogue's order."""
        if scope.user_id is None:
            return []
        async with self._transactions.begin(scope, read_only=True) as session:
            held = await bindings(
                session,
                ConnectionRecord.user_id == scope.user_id,
                ConnectionRecord.org_id.is_(None),
            )
        by_app = {found.view.app: found for found in held}
        shared = Counter(found.grant_id for found in held)
        offered = self._offers.offered(scope.user_id)
        rows = []
        for app, spec in CATALOGUE.items():
            if app not in offered and app not in by_app:
                continue
            found = by_app.get(app)
            view = None if found is None else found.view
            rows.append(
                ConnectorRow(spec, view, self._remains(found, shared), self._reconnect_by(found))
            )
        return rows

    async def row(self, scope: TenancyScope, app: App) -> ConnectorRow:
        """One app's row; `NotConnectedError` when it is neither offered nor connected."""
        for row in await self.rows(scope):
            if row.spec.app is app:
                return row
        raise NotConnectedError

    def _remains(self, found: ConnectionBinding | None, shared: Counter[UUID]) -> bool:
        if found is None:
            return False
        if shared[found.grant_id] > 1:
            return True
        client = self._registry.client(found.client_key)
        return client is None or client.adapter.descriptor.revocation.kind is RevocationKind.NONE

    def _reconnect_by(self, found: ConnectionBinding | None) -> datetime | None:
        if found is None:
            return None
        client = self._registry.client(found.client_key)
        consent = found.view.provider_meta.get("consent_at")
        if client is None or client.consent_lifetime is None or not isinstance(consent, str):
            return None
        try:
            return datetime.fromisoformat(consent) + client.consent_lifetime
        except ValueError:
            return None
