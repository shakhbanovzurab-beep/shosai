"""A capability port's call through the connection's provider session, to the adapter of the
connection's app; an app without one is the port's own `unsupported` error (plan §3.3)."""

from collections.abc import Awaitable, Callable, Mapping
from uuid import UUID

from shosai.core.kernel.errors import AppError
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.connectors.application.provider_access import ConnectorProviderAccess
from shosai.features.connectors.contracts.provider import ProviderSession
from shosai.features.connectors.domain.catalogue import App


class CapabilitySessions[A]:
    """The adapters of one capability by app, and the sessions they run in."""

    def __init__(
        self,
        access: ConnectorProviderAccess,
        adapters: Mapping[App, A],
        unsupported: Callable[[], AppError],
    ) -> None:
        self._access = access
        self._adapters = adapters
        self._unsupported = unsupported

    async def run[T](
        self,
        scope: TenancyScope,
        connection_id: UUID,
        call: Callable[[A, ProviderSession], Awaitable[T]],
    ) -> T:
        """One call of the connection's adapter inside its provider session."""
        async with self._access.open(scope, connection_id) as session:
            adapter = self._adapters.get(session.connection.app)
            if adapter is None:
                raise self._unsupported()
            return await call(adapter, session)

    def adapter(self, app: str) -> A | None:
        """The adapter of an app named by a provider's callback; None for an unknown one."""
        try:
            return self._adapters.get(App(app))
        except ValueError:
            return None
