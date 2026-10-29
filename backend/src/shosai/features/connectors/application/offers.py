"""Which apps the cabinet offers (CN-D4): those a consumer uses, with an application to use.

Each consumer slice binds `CONNECTOR_USES` with the apps it uses; an app reached by OAuth is
offered once its OAuth application is configured, an app reached by a password, a key or a
hook URL needs nothing more. A person's existing connection is listed whether or not its app
is still offered, so it can always be disconnected. Gmail's restricted scope waits for CASA
(CN-D5): until public Gmail is turned on, it is offered only to the owner's testers.
"""

from dataclasses import dataclass, field
from uuid import UUID

from shosai.core.ports.directory import PortDirectory
from shosai.features.connectors.contracts import CONNECTOR_USES
from shosai.features.connectors.domain.catalogue import App, AuthKind, spec_of
from shosai.features.connectors.infrastructure.providers.base import ProviderRegistry


@dataclass(frozen=True, slots=True)
class GmailAccess:
    """Who may connect Gmail: everyone once CASA is passed, the listed testers until then."""

    public: bool = False
    testers: frozenset[UUID] = field(default_factory=frozenset)

    def allows(self, user_id: UUID | None) -> bool:
        """Whether this person may connect Gmail."""
        return self.public or (user_id is not None and user_id in self.testers)


class Offers:
    """The offered apps of this process, read when asked: ports bind after every slice."""

    def __init__(
        self, ports: PortDirectory, registry: ProviderRegistry, gmail: GmailAccess | None = None
    ) -> None:
        self._ports = ports
        self._registry = registry
        self._gmail = gmail or GmailAccess()

    def offered(self, user_id: UUID | None = None) -> frozenset[App]:
        """The apps this person may connect now."""
        used = frozenset(app for uses in self._ports.all(CONNECTOR_USES) for app in uses.apps)
        configured = self._registry.configured()
        gmail = self._gmail.allows(user_id)
        return frozenset(
            app
            for app in used
            if self.reachable(app, configured) and (app is not App.GMAIL or gmail)
        )

    @staticmethod
    def reachable(app: App, configured: frozenset[str]) -> bool:
        """Whether Shosai can connect the app with what this deployment configured."""
        spec = spec_of(app)
        return spec.auth[0] is not AuthKind.OAUTH2 or spec.client_key in configured
