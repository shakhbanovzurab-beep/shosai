"""Google: the code flow with PKCE and the Sign in with Google button (draft `google.py`).

Both paths end in an ID token, checked here against Google's published keys: RS256, the
audience this application's client id, the issuer Google, an expiry. The keys are fetched
without blocking the event loop and kept a day; an unknown key id refetches them once.
The address counts as verified only when Google says so in `email_verified`.
"""

import time
from typing import Final
from urllib.parse import urlencode

import httpx
import jwt
from pydantic import SecretStr

from shosai.features.identity.domain.social import Provider, SocialIdentity
from shosai.features.identity.infrastructure.social.base import (
    SocialProviderFailedError,
    json_object,
    required,
    text,
)

AUTHORIZE_URL: Final = "https://accounts.google.com/o/oauth2/v2/auth"
EXCHANGE_URL: Final = "https://oauth2.googleapis.com/token"
KEYS_URL: Final = "https://www.googleapis.com/oauth2/v3/certs"
ISSUERS: Final = ("accounts.google.com", "https://accounts.google.com")
KEYS_KEPT_SECONDS: Final = 24 * 3600


class Google:
    """The Google client of this application."""

    key: Final = Provider.GOOGLE

    def __init__(
        self, http: httpx.AsyncClient, client_id: str, secret: SecretStr, redirect_uri: str
    ) -> None:
        self._http = http
        self._client_id = client_id
        self._secret = secret
        self._redirect_uri = redirect_uri
        self._keys: dict[str, jwt.PyJWK] = {}
        self._keys_read_at = 0.0

    def authorize_url(self, state: str, challenge: str) -> str:
        """Google's account chooser with the PKCE challenge."""
        query = {
            "response_type": "code", "client_id": self._client_id,
            "redirect_uri": self._redirect_uri, "scope": "openid email profile", "state": state,
            "code_challenge": challenge, "code_challenge_method": "S256",
            "access_type": "online", "prompt": "select_account",
        }  # fmt: skip
        return f"{AUTHORIZE_URL}?{urlencode(query)}"

    async def identify(self, code: str, verifier: str, device_id: str | None) -> SocialIdentity:
        """Exchange the code and check the ID token it returns."""
        del device_id
        form = {
            "grant_type": "authorization_code", "code": code, "client_id": self._client_id,
            "client_secret": self._secret.get_secret_value(), "code_verifier": verifier,
            "redirect_uri": self._redirect_uri,
        }  # fmt: skip
        try:
            response = await self._http.post(EXCHANGE_URL, data=form)
        except httpx.HTTPError as error:
            message = "google: обмен кода не удался"
            raise SocialProviderFailedError(message) from error
        payload = await json_object(response, "google: токен")
        return await self.identify_token(required(payload, "id_token", "google"))

    async def identify_token(self, token: str) -> SocialIdentity:
        """The person of an ID token issued by Google to this application."""
        try:
            key_id = jwt.get_unverified_header(token).get("kid")
        except jwt.InvalidTokenError as error:
            message = "google: токен не разобран"
            raise SocialProviderFailedError(message) from error
        key = await self._key(str(key_id))
        try:
            claims = jwt.decode(
                token, key, algorithms=["RS256"], audience=self._client_id,
                issuer=list(ISSUERS), options={"require": ["exp", "iat", "aud", "iss", "sub"]},
            )  # fmt: skip
        except jwt.InvalidTokenError as error:
            message = "google: токен не прошёл проверку или выдан другому приложению"
            raise SocialProviderFailedError(message) from error
        email = text(claims, "email")
        return SocialIdentity(
            provider=self.key,
            subject=required(claims, "sub", "google"),
            email=email.lower() if email else None,
            email_verified=email is not None and claims.get("email_verified") is True,
            display_name=text(claims, "name") or text(claims, "given_name"),
        )

    async def _key(self, key_id: str) -> jwt.PyJWK:
        fresh = time.monotonic() - self._keys_read_at < KEYS_KEPT_SECONDS
        if key_id not in self._keys or not fresh:
            await self._read_keys()
        key = self._keys.get(key_id)
        if key is None:
            message = "google: неизвестный ключ подписи"
            raise SocialProviderFailedError(message)
        return key

    async def _read_keys(self) -> None:
        try:
            response = await self._http.get(KEYS_URL)
        except httpx.HTTPError as error:
            message = "google: ключи не прочитаны"
            raise SocialProviderFailedError(message) from error
        keys = (await json_object(response, "google: ключи")).get("keys")
        if not isinstance(keys, list):
            message = "google: нет ключей"
            raise SocialProviderFailedError(message)
        self._keys = {
            str(item["kid"]): jwt.PyJWK(item)
            for item in keys
            if isinstance(item, dict) and "kid" in item
        }
        self._keys_read_at = time.monotonic()
