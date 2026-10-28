"""The connectors slice as composition sees it (connectors plan §3.1, ADR 0075).

Step 1 published the contracts and the domain. Step 2 the tables in each home — grants, their
secrets, the apps on them — with row-level security that keeps a personal row its person's
alone, and the handler of what connectors holds of a person. Step 3 the OAuth core: a flow
started by `POST /v1/connectors/{app}/authorize` with PKCE, a one-time state in Valkey and a
browser binder, finished at `GET /v1/connectors/oauth/{provider}/callback` into a grant, its
encrypted secrets and the app on it. It also brings a workspace's installations for chats
and the draft's callback paths, which answer an expired authorization.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from shosai.core.account_data.handlers import ACCOUNT_DATA_HANDLERS
from shosai.core.crypto.key_ring import FernetKeyRing
from shosai.core.features import CoreServices, FeatureModule, FeatureParts
from shosai.features.connectors.application.account_data import (
    ACCOUNT_DATA,
    ConnectorsAccountData,
)
from shosai.features.connectors.application.authorize import Authorizer, AuthorizeTools
from shosai.features.connectors.application.callback import CallbackTools, Completer
from shosai.features.connectors.application.installation_audit import InstallationAudit
from shosai.features.connectors.application.installations import WorkspaceInstallations
from shosai.features.connectors.application.offers import Offers
from shosai.features.connectors.channels.http.connect_routes import build_connect_router
from shosai.features.connectors.contracts import INSTALLATIONS
from shosai.features.connectors.contracts.events import CONNECTOR_EVENTS
from shosai.features.connectors.infrastructure.oauth.flow_store import FlowStore
from shosai.features.connectors.infrastructure.providers.base import ProviderRegistry
from shosai.features.connectors.infrastructure.providers.configured import configured_clients
from shosai.features.connectors.infrastructure.store.records import CONNECTOR_MODELS
from shosai.features.connectors.infrastructure.transport.http_client import (
    open_connectors_http,
)
from shosai.features.connectors.settings import ConnectorsSettings


@asynccontextmanager
async def build(services: CoreServices) -> AsyncIterator[FeatureParts]:
    """Connectors' parts for this process."""
    settings = services.settings.features.get(ConnectorsSettings)
    public = settings.connectors_public_base_url or services.settings.email.public_base_url
    base_url = str(public).rstrip("/")
    crypto = services.settings.crypto
    keys = FernetKeyRing.from_settings(crypto) if crypto.fernet_key is not None else None
    registry = ProviderRegistry(configured_clients(settings))
    flows, audit = FlowStore(services.valkey), InstallationAudit(services.ports)
    async with open_connectors_http() as http:
        authorize = AuthorizeTools(
            Offers(services.ports, registry), registry, flows, base_url, sealing=keys is not None
        )
        authorizer = Authorizer(services.transactions, authorize)
        completer = Completer(
            services.transactions,
            CallbackTools(flows, registry, http, keys, services.outbox, audit, base_url),
        )
        yield FeatureParts(
            http_routers=(build_connect_router((authorizer, completer), services.ports),),
            provides=(
                ACCOUNT_DATA_HANDLERS.bind(ConnectorsAccountData(services.transactions)),
                INSTALLATIONS.bind(WorkspaceInstallations(authorizer, audit, services.outbox)),
            ),
        )


CONNECTORS = FeatureModule(
    name="connectors",
    build=build,
    models=CONNECTOR_MODELS,
    events=CONNECTOR_EVENTS,
    settings=(ConnectorsSettings,),
    account_data=(ACCOUNT_DATA,),
)
