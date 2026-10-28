"""Which apps the cabinet offers (CN-D4): those a consumer uses, with an application to use.

Each consumer slice binds `CONNECTOR_USES` with the apps it uses; an app reached by OAuth is
offered once its OAuth application is configured, an app reached by a password, a key or a
hook URL needs nothing more. A person's existing connection is listed whether or not its app
is still offered, so it can always be disconnected.
"""

from shosai.core.ports.directory import PortDirectory
from shosai.features.connectors.contracts import CONNECTOR_USES
from shosai.features.connectors.domain.catalogue import App, AuthKind, spec_of
from shosai.features.connectors.infrastructure.providers.base import ProviderRegistry


class Offers:
    """The offered apps of this process, read when asked: ports bind after every slice."""

    def __init__(self, ports: PortDirectory, registry: ProviderRegistry) -> None:
        self._ports = ports
        self._registry = registry

    def offered(self) -> frozenset[App]:
        """The apps a person may connect now."""
        used = frozenset(app for uses in self._ports.all(CONNECTOR_USES) for app in uses.apps)
        configured = self._registry.configured()
        return frozenset(app for app in used if self.reachable(app, configured))

    @staticmethod
    def reachable(app: App, configured: frozenset[str]) -> bool:
        """Whether Shosai can connect the app with what this deployment configured."""
        spec = spec_of(app)
        return spec.auth[0] is not AuthKind.OAUTH2 or spec.client_key in configured
