"""Browsing a person's connected app for a scope picker (plan §3.7).

The app's browser — brought by its provider's step — lists one kind of place through the
person's own connection, inside a provider session, so quotas, `Retry-After` and refresh
apply as to every call. An app without a browser, or a kind it does not list, is
`resources_unsupported`.
"""

from collections.abc import Mapping
from http import HTTPStatus
from typing import Protocol

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.connectors.application.provider_access import ConnectorProviderAccess
from shosai.features.connectors.contracts import NotConnectedError, ProviderSession
from shosai.features.connectors.contracts.resources import ResourcePage, ResourceQuery
from shosai.features.connectors.domain.catalogue import App
from shosai.features.connectors.infrastructure.store.connection_reads import bindings
from shosai.features.connectors.infrastructure.store.records import ConnectionRecord


class ResourcesUnsupportedError(AppError):
    """The app lists no places of that kind."""

    def __init__(self) -> None:
        super().__init__("resources_unsupported", HTTPStatus.NOT_FOUND)


class ResourceBrowser(Protocol):
    """One app's listing of its places."""

    @property
    def kinds(self) -> frozenset[str]:
        """The kinds of places this app lists."""
        ...

    async def browse(self, session: ProviderSession, query: ResourceQuery) -> ResourcePage:
        """A page of places of the query's kind."""
        ...


class Resources:
    """Lists the places of a person's connected apps."""

    def __init__(
        self,
        transactions: HomeTransactions,
        access: ConnectorProviderAccess,
        browsers: Mapping[App, ResourceBrowser],
    ) -> None:
        self._transactions = transactions
        self._access = access
        self._browsers = browsers

    async def browse(self, scope: TenancyScope, app: App, query: ResourceQuery) -> ResourcePage:
        """A page of the person's places in the app."""
        browser = self._browsers.get(app)
        if browser is None or query.kind not in browser.kinds:
            raise ResourcesUnsupportedError
        if scope.user_id is None:
            raise NotConnectedError
        async with self._transactions.begin(scope, read_only=True) as session:
            found = await bindings(
                session, ConnectionRecord.user_id == scope.user_id,
                ConnectionRecord.org_id.is_(None), ConnectionRecord.app == app.value,
            )  # fmt: skip
        if not found:
            raise NotConnectedError
        async with self._access.open(scope, found[0].view.id) as provider:
            return await browser.browse(provider, query)
