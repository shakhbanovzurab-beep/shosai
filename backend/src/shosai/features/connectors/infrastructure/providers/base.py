"""What a provider's adapter gives the core, and the registry of the configured ones.

An adapter carries its descriptor, reads the tokens out of its token endpoint's answer
(Slack keeps a person's token under `authed_user`), says who the account is, and maps the
provider's own callback errors (Microsoft's admin-consent refusals) to the cabinet's codes.
The registry holds an adapter per OAuth application whose credentials are configured; an
app whose application is missing is not offered (CN-D4).
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

import httpx

from shosai.features.connectors.domain.catalogue import Provider
from shosai.features.connectors.domain.descriptors import ProviderDescriptor
from shosai.features.connectors.domain.flows import FlowError
from shosai.features.connectors.infrastructure.oauth.tokens import ClientCredentials, TokenSet

# Отказ человека на экране согласия — общий код RFC 6749 §4.1.2.1.
ACCESS_DENIED = "access_denied"


@dataclass(frozen=True, slots=True)
class AccountIdentity:
    """Who the provider account is: its stable id, a label for screens, non-secret facts."""

    external_account_id: str
    label: str | None
    meta: Mapping[str, object] = field(default_factory=dict)


class ProviderAdapter(Protocol):
    """One OAuth application's provider, as the connect flow uses it."""

    @property
    def descriptor(self) -> ProviderDescriptor:
        """The provider's endpoints and rules."""
        ...

    def tokens(self, payload: Mapping[str, object], now: datetime) -> TokenSet:
        """The tokens of a successful token answer."""
        ...

    async def identify(self, http: httpx.AsyncClient, tokens: TokenSet) -> AccountIdentity:
        """The account the tokens act for."""
        ...

    def callback_error(self, error: str, description: str | None) -> FlowError | None:
        """The cabinet's code for a provider's own callback error; None for a refusal."""
        ...


@dataclass(frozen=True, slots=True)
class ConfiguredClient:
    """An adapter and the credentials of its OAuth application."""

    adapter: ProviderAdapter
    credentials: ClientCredentials


class ProviderRegistry:
    """The configured OAuth applications by their client key."""

    def __init__(self, clients: Mapping[str, ConfiguredClient]) -> None:
        for key, client in clients.items():
            if client.adapter.descriptor.client_key != key:
                message = (
                    f"приложение {key}: ключ описателя — {client.adapter.descriptor.client_key}"
                )
                raise ValueError(message)
        self._clients = dict(clients)

    def client(self, client_key: str) -> ConfiguredClient | None:
        """The configured application of a key, or None."""
        return self._clients.get(client_key)

    def configured(self) -> frozenset[str]:
        """The keys of every configured application."""
        return frozenset(self._clients)

    def of_provider(self, provider: Provider) -> tuple[str, ...]:
        """The configured applications of one provider, by key."""
        return tuple(
            key for key, client in self._clients.items()
            if client.adapter.descriptor.provider is provider
        )  # fmt: skip
