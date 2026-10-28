"""The `connectors.provider_access` binding: sessions on connections a scope may read.

The connection is read in the caller's scope, under its row-level security; one that needs
its person is refused at once, without a provider call; one whose OAuth application this
deployment no longer configures is unavailable. The session itself is opened outside any
transaction (§14 rule 1), and lives for one request or task.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.connectors.contracts import (
    ConnectionStatus,
    NeedsReconnectError,
    NotConnectedError,
    Problem,
)
from shosai.features.connectors.contracts.provider import ProviderUnavailableError
from shosai.features.connectors.infrastructure.providers.base import ProviderRegistry
from shosai.features.connectors.infrastructure.store.connection_reads import binding
from shosai.features.connectors.infrastructure.transport.session import (
    AuthorizedSession,
    SessionParts,
    SessionTarget,
)


class ConnectorProviderAccess:
    """Opens authorized sessions."""

    def __init__(
        self, transactions: HomeTransactions, registry: ProviderRegistry, parts: SessionParts
    ) -> None:
        self._transactions = transactions
        self._registry = registry
        self._parts = parts

    @asynccontextmanager
    async def open(
        self, scope: TenancyScope, connection_id: UUID
    ) -> AsyncIterator[AuthorizedSession]:
        """A session on the connection, or the reason there is none."""
        async with self._transactions.begin(scope, read_only=True) as session:
            found = await binding(session, connection_id)
        if found is None:
            raise NotConnectedError
        if found.view.status is not ConnectionStatus.ACTIVE:
            raise NeedsReconnectError(found.view.problem or Problem.GRANT_REVOKED)
        client = self._registry.client(found.client_key)
        if client is None:
            raise ProviderUnavailableError
        owner = TenancyScope(scope.home, found.view.user_id, found.view.org_id)
        target = SessionTarget(owner, found.view, found.grant_id, client.adapter.descriptor)
        yield AuthorizedSession(self._parts, target)
