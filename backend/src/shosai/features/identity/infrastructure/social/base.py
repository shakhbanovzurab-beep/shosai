"""What every provider client offers, and how a provider failure is told (ADR 0045).

A client builds the authorize URL of the code flow with PKCE, and turns the code into a
`SocialIdentity`; Yandex and Google can also turn a token their widget handed the browser
into one. Every failure — network, a refusal, an unexpected answer, a token issued to
another application — is a `SocialProviderFailedError`, which the callback turns into a
redirect, never JSON. Provider tokens are used once and never stored.
"""

from typing import Final, Protocol

import httpx

from shosai.features.identity.domain.social import Provider, SocialIdentity

TIMEOUT: Final = httpx.Timeout(10.0, connect=3.0)


class SocialProviderFailedError(Exception):
    """The provider did not confirm who the person is; the reason is for the log only."""


class SocialProvider(Protocol):
    """One provider's code flow."""

    @property
    def key(self) -> Provider:
        """Which provider this client speaks to."""
        ...

    def authorize_url(self, state: str, challenge: str) -> str:
        """Where the browser goes to sign in at the provider."""
        ...

    async def identify(self, code: str, verifier: str, device_id: str | None) -> SocialIdentity:
        """The person behind an authorization code."""
        ...


class WidgetProvider(SocialProvider, Protocol):
    """A provider whose widget gives the browser a token the server can check."""

    async def identify_token(self, token: str) -> SocialIdentity:
        """The person behind a widget token issued to this application."""
        ...


async def json_object(response: httpx.Response, what: str) -> dict[str, object]:
    """The JSON object of a successful answer, or `SocialProviderFailedError`."""
    if response.status_code != httpx.codes.OK:
        message = f"{what}: статус {response.status_code}"
        raise SocialProviderFailedError(message)
    try:
        payload = response.json()
    except ValueError as error:
        message = f"{what}: ответ не JSON"
        raise SocialProviderFailedError(message) from error
    if not isinstance(payload, dict):
        message = f"{what}: ответ не объект"
        raise SocialProviderFailedError(message)
    return payload


def text(payload: dict[str, object], name: str) -> str | None:
    """A non-empty string field, stripped, or None."""
    value = payload.get(name)
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def required(payload: dict[str, object], name: str, what: str) -> str:
    """A field the identity cannot do without."""
    value = text(payload, name)
    if value is None:
        message = f"{what}: нет поля {name}"
        raise SocialProviderFailedError(message)
    return value
