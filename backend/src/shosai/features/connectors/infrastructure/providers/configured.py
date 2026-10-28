"""The OAuth applications this deployment configured, each with its provider's adapter.

A provider's step adds its adapter here with the settings that hold its application's id and
secret; an application without both is not configured, and its apps are not offered. A Google
project in Testing gives seven-day refresh tokens, which the cabinet tells ahead.
"""

from collections.abc import Mapping
from datetime import timedelta

from pydantic import SecretStr

from shosai.features.connectors.infrastructure.oauth.tokens import ClientCredentials
from shosai.features.connectors.infrastructure.providers.atlassian import AtlassianAdapter
from shosai.features.connectors.infrastructure.providers.base import (
    ConfiguredClient,
    ProviderAdapter,
)
from shosai.features.connectors.infrastructure.providers.google import (
    GOOGLE,
    GOOGLE_MAIL,
    TESTING_LIFETIME,
    GoogleAdapter,
)
from shosai.features.connectors.settings import ConnectorsSettings


def _client(
    adapter: ProviderAdapter,
    pair: tuple[str | None, SecretStr | None],
    lifetime: timedelta | None = None,
) -> ConfiguredClient | None:
    client_id, secret = pair
    if client_id is None or secret is None:
        return None
    return ConfiguredClient(adapter, ClientCredentials(client_id, secret), lifetime)


def configured_clients(settings: ConnectorsSettings) -> Mapping[str, ConfiguredClient]:
    """Every configured application by its client key."""
    s = settings
    candidates = {
        "atlassian": _client(
            AtlassianAdapter(),
            (s.connectors_atlassian_client_id, s.connectors_atlassian_client_secret),
        ),
        "google": _client(
            GoogleAdapter(GOOGLE),
            (s.connectors_google_client_id, s.connectors_google_client_secret),
            TESTING_LIFETIME if s.connectors_google_testing else None,
        ),
        "google_mail": _client(
            GoogleAdapter(GOOGLE_MAIL),
            (s.connectors_google_mail_client_id, s.connectors_google_mail_client_secret),
            TESTING_LIFETIME if s.connectors_google_mail_testing else None,
        ),
    }
    return {key: client for key, client in candidates.items() if client is not None}
