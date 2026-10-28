"""The connectors slice as composition sees it (connectors plan §3.1, ADR 0075).

Step 1 published the contracts — `CONNECTIONS`, `PROVIDER_ACCESS`, `INSTALLATIONS`,
`CONNECTOR_USES` and the three events — and the domain: the catalogue of apps with their
providers, capabilities and scopes, the provider descriptor, the states of grants and
connections with their problems, the rules of a connect flow and of a refresh.
"""

from shosai.core.features import FeatureModule
from shosai.features.connectors.contracts.events import CONNECTOR_EVENTS

CONNECTORS = FeatureModule(name="connectors", events=CONNECTOR_EVENTS)
