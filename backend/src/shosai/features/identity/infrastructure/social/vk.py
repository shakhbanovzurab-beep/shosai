"""VK ID: OAuth 2.1 with PKCE and `device_id`, no client secret (draft `vk.py`).

VK ID returns `device_id` with the code and wants it back in the exchange. The address
VK returns is not taken as proof of ownership: a VK email never links to an existing
account by itself (ADR 0045 point 10); the person signs in first and links VK there.
"""

from typing import Final
from urllib.parse import urlencode

import httpx

from shosai.features.identity.domain.social import Provider, SocialIdentity
from shosai.features.identity.infrastructure.social.base import (
    SocialProviderFailedError,
    json_object,
    required,
    text,
)

AUTHORIZE_URL: Final = "https://id.vk.com/authorize"
EXCHANGE_URL: Final = "https://id.vk.com/oauth2/auth"
USERINFO_URL: Final = "https://id.vk.com/oauth2/user_info"


class Vk:
    """The VK ID client of this application."""

    key: Final = Provider.VK

    def __init__(self, http: httpx.AsyncClient, client_id: str, redirect_uri: str) -> None:
        self._http = http
        self._client_id = client_id
        self._redirect_uri = redirect_uri

    def authorize_url(self, state: str, challenge: str) -> str:
        """The VK ID page with the PKCE challenge and the email scope."""
        query = {
            "response_type": "code", "client_id": self._client_id,
            "redirect_uri": self._redirect_uri, "state": state, "code_challenge": challenge,
            "code_challenge_method": "S256", "scope": "email",
        }  # fmt: skip
        return f"{AUTHORIZE_URL}?{urlencode(query)}"

    async def identify(self, code: str, verifier: str, device_id: str | None) -> SocialIdentity:
        """Exchange the code with the device id VK returned, then read the person."""
        if not device_id:
            message = "vk: нет device_id"
            raise SocialProviderFailedError(message)
        form = {
            "grant_type": "authorization_code", "code": code, "code_verifier": verifier,
            "client_id": self._client_id, "device_id": device_id,
            "redirect_uri": self._redirect_uri,
        }  # fmt: skip
        try:
            response = await self._http.post(EXCHANGE_URL, data=form)
            token = required(await json_object(response, "vk: токен"), "access_token", "vk")
            info = await self._http.post(
                USERINFO_URL, data={"client_id": self._client_id, "access_token": token}
            )
        except httpx.HTTPError as error:
            message = "vk: обмен кода не удался"
            raise SocialProviderFailedError(message) from error
        user = (await json_object(info, "vk: профиль")).get("user")
        if not isinstance(user, dict):
            message = "vk: нет профиля"
            raise SocialProviderFailedError(message)
        email = text(user, "email")
        name = " ".join(
            part for part in (text(user, "first_name"), text(user, "last_name")) if part
        )
        return SocialIdentity(
            provider=self.key,
            subject=required(user, "user_id", "vk"),
            email=email.lower() if email else None,
            email_verified=False,
            display_name=name or None,
        )
