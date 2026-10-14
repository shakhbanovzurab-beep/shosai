"""The provider clients this deployment has credentials for, over one HTTP client."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx

from shosai.features.identity.domain.social import Provider
from shosai.features.identity.infrastructure.social.base import TIMEOUT, SocialProvider
from shosai.features.identity.infrastructure.social.github import GitHub
from shosai.features.identity.infrastructure.social.google import Google
from shosai.features.identity.infrastructure.social.vk import Vk
from shosai.features.identity.infrastructure.social.yandex import Yandex
from shosai.features.identity.settings import IdentitySettings


def callback_uri(base_url: str, provider: Provider) -> str:
    """The address registered with the provider."""
    return f"{base_url}/v1/auth/social/{provider.value}/callback"


def provider_clients(
    http: httpx.AsyncClient, settings: IdentitySettings, base_url: str
) -> dict[Provider, SocialProvider]:
    """A client per provider whose credentials are set."""
    found: dict[Provider, SocialProvider] = {}
    s = settings
    if s.identity_yandex_client_id and s.identity_yandex_client_secret:
        found[Provider.YANDEX] = Yandex(
            http, s.identity_yandex_client_id, s.identity_yandex_client_secret,
            callback_uri(base_url, Provider.YANDEX),
        )  # fmt: skip
    if s.identity_vk_client_id:
        found[Provider.VK] = Vk(http, s.identity_vk_client_id, callback_uri(base_url, Provider.VK))
    if s.identity_google_client_id and s.identity_google_client_secret:
        found[Provider.GOOGLE] = Google(
            http, s.identity_google_client_id, s.identity_google_client_secret,
            callback_uri(base_url, Provider.GOOGLE),
        )  # fmt: skip
    if s.identity_github_client_id and s.identity_github_client_secret:
        found[Provider.GITHUB] = GitHub(
            http, s.identity_github_client_id, s.identity_github_client_secret,
            callback_uri(base_url, Provider.GITHUB),
        )  # fmt: skip
    return found


@asynccontextmanager
async def open_provider_http() -> AsyncIterator[httpx.AsyncClient]:
    """The HTTP client of every provider call: bounded timeouts, no retries."""
    async with httpx.AsyncClient(timeout=TIMEOUT) as http:
        yield http
