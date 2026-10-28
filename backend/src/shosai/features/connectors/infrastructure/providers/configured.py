"""The OAuth applications this deployment configured, each with its provider's adapter.

A provider's step adds its adapter here with the settings that hold its application's id and
secret; an application without both is not configured, and its apps are not offered.
"""

from collections.abc import Mapping

from shosai.features.connectors.infrastructure.providers.base import ConfiguredClient
from shosai.features.connectors.settings import ConnectorsSettings


def configured_clients(settings: ConnectorsSettings) -> Mapping[str, ConfiguredClient]:
    """Every configured application by its client key; no provider is wired yet."""
    del settings
    return {}
