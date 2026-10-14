"""Yandex ID: the code flow with PKCE and the widget's implicit token (draft `yandex.py`).

Scopes come from the application's registration (`login:email`, `login:info`). The
address is the account's `default_email`, which Yandex confirmed. Every token, from the
code exchange or from the widget, is checked to be issued to this application: a token
another app obtained would otherwise open the person's account here.
"""

from typing import Final
from urllib.parse import urlencode

import httpx
from pydantic import SecretStr

from shosai.features.identity.domain.social import Provider, SocialIdentity
from shosai.features.identity.infrastructure.social.base import (
    SocialProviderFailedError,
    json_object,
    required,
    text,
)

AUTHORIZE_URL: Final = "https://oauth.yandex.ru/authorize"
EXCHANGE_URL: Final = "https://oauth.yandex.ru/token"
USERINFO_URL: Final = "https://login.yandex.ru/info"


class Yandex:
    """The Yandex ID client of this application."""

    key: Final = Provider.YANDEX

    def __init__(
        self, http: httpx.AsyncClient, client_id: str, secret: SecretStr, redirect_uri: str
    ) -> None:
        self._http = http
        self._client_id = client_id
        self._secret = secret
        self._redirect_uri = redirect_uri

    def authorize_url(self, state: str, challenge: str) -> str:
        """The Yandex consent page with the PKCE challenge."""
        query = {
            "response_type": "code", "client_id": self._client_id,
            "redirect_uri": self._redirect_uri, "state": state, "code_challenge": challenge,
            "code_challenge_method": "S256", "force_confirm": "yes",
        }  # fmt: skip
        return f"{AUTHORIZE_URL}?{urlencode(query)}"

    async def identify(self, code: str, verifier: str, device_id: str | None) -> SocialIdentity:
        """Exchange the code, then read the person."""
        del device_id
        form = {
            "grant_type": "authorization_code", "code": code, "client_id": self._client_id,
            "client_secret": self._secret.get_secret_value(), "code_verifier": verifier,
            "redirect_uri": self._redirect_uri,
        }  # fmt: skip
        try:
            response = await self._http.post(EXCHANGE_URL, data=form)
        except httpx.HTTPError as error:
            message = "яндекс: обмен кода не удался"
            raise SocialProviderFailedError(message) from error
        token = required(await json_object(response, "яндекс: токен"), "access_token", "яндекс")
        return await self.identify_token(token)

    async def identify_token(self, token: str) -> SocialIdentity:
        """The person behind a token, which must be issued to this application."""
        try:
            response = await self._http.get(
                USERINFO_URL,
                params={"format": "json"},
                headers={"Authorization": f"OAuth {token}"},
            )
        except httpx.HTTPError as error:
            message = "яндекс: профиль не прочитан"
            raise SocialProviderFailedError(message) from error
        payload = await json_object(response, "яндекс: профиль")
        if payload.get("client_id") != self._client_id:
            message = "яндекс: токен выдан другому приложению"
            raise SocialProviderFailedError(message)
        email = text(payload, "default_email")
        return SocialIdentity(
            provider=self.key,
            subject=required(payload, "id", "яндекс"),
            email=email.lower() if email else None,
            # default_email — адрес аккаунта Яндекса, подтверждённый самим Яндексом.
            email_verified=email is not None,
            display_name=text(payload, "real_name") or text(payload, "display_name"),
        )
