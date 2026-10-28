"""The OAuth applications this deployment configured, each with its provider's adapter.

A provider's step adds its adapter here with the settings that hold its application's id and
secret; an application without both is not configured, and its apps are not offered.
"""

from collections.abc import Mapping

from shosai.features.connectors.infrastructure.oauth.tokens import ClientCredentials
from shosai.features.connectors.infrastructure.providers.atlassian import AtlassianAdapter
from shosai.features.connectors.infrastructure.providers.base import ConfiguredClient
from shosai.features.connectors.settings import ConnectorsSettings


def configured_clients(settings: ConnectorsSettings) -> Mapping[str, ConfiguredClient]:
    """Every configured application by its client key."""
    clients: dict[str, ConfiguredClient] = {}
    atlassian_id, atlassian_secret = (
        settings.connectors_atlassian_client_id, settings.connectors_atlassian_client_secret
    )  # fmt: skip
    if atlassian_id is not None and atlassian_secret is not None:
        credentials = ClientCredentials(atlassian_id, atlassian_secret)
        clients["atlassian"] = ConfiguredClient(AtlassianAdapter(), credentials)
    return clients
