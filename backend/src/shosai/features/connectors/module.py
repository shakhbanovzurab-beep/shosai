"""The connectors slice as composition sees it (connectors plan §3.1, ADR 0075).

Step 1 published the contracts — `CONNECTIONS`, `PROVIDER_ACCESS`, `INSTALLATIONS`,
`CONNECTOR_USES` and the three events — and the domain: the catalogue of apps with their
providers, capabilities and scopes, the provider descriptor, the states of grants and
connections with their problems, the rules of a connect flow and of a refresh. Step 2 the
tables in each home — grants, their secrets, the apps on them — with row-level security that
keeps a personal row its person's alone, and the handler of what connectors holds of a person.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from shosai.core.account_data.handlers import ACCOUNT_DATA_HANDLERS
from shosai.core.features import CoreServices, FeatureModule, FeatureParts
from shosai.features.connectors.application.account_data import (
    ACCOUNT_DATA,
    ConnectorsAccountData,
)
from shosai.features.connectors.contracts.events import CONNECTOR_EVENTS
from shosai.features.connectors.infrastructure.store.records import CONNECTOR_MODELS


@asynccontextmanager
async def build(services: CoreServices) -> AsyncIterator[FeatureParts]:
    """Connectors' parts for this process."""
    yield FeatureParts(
        provides=(ACCOUNT_DATA_HANDLERS.bind(ConnectorsAccountData(services.transactions)),),
    )


CONNECTORS = FeatureModule(
    name="connectors",
    build=build,
    models=CONNECTOR_MODELS,
    events=CONNECTOR_EVENTS,
    account_data=(ACCOUNT_DATA,),
)
