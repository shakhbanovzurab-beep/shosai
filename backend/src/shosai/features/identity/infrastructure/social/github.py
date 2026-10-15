"""GitHub: an OAuth App's code flow with PKCE (draft `github.py`).

The address is the primary verified one, else any verified one; GitHub's no-reply
addresses are not addresses. Without one, a new person cannot register through GitHub.
"""

from typing import Final
from urllib.parse import urlencode

import httpx
import structlog
from pydantic import SecretStr

from shosai.features.identity.domain.social import Provider, SocialIdentity
from shosai.features.identity.infrastructure.social.base import (
    SocialProviderFailedError,
    json_object,
    required,
    text,
)

AUTHORIZE_URL: Final = "https://github.com/login/oauth/authorize"
EXCHANGE_URL: Final = "https://github.com/login/oauth/access_token"
USER_URL: Final = "https://api.github.com/user"
EMAILS_URL: Final = "https://api.github.com/user/emails"
log = structlog.stdlib.get_logger(__name__)
NO_REPLY: Final = "@users.noreply.github.com"


class GitHub:
    """The GitHub OAuth App of this application."""

    key: Final = Provider.GITHUB

    def __init__(
        self, http: httpx.AsyncClient, client_id: str, secret: SecretStr, redirect_uri: str
    ) -> None:
        self._http = http
        self._client_id = client_id
        self._secret = secret
        self._redirect_uri = redirect_uri

    def authorize_url(self, state: str, challenge: str) -> str:
        """GitHub's consent page with the PKCE challenge."""
        query = {
            "client_id": self._client_id, "redirect_uri": self._redirect_uri,
            "scope": "read:user user:email", "state": state, "code_challenge": challenge,
            "code_challenge_method": "S256",
        }  # fmt: skip
        return f"{AUTHORIZE_URL}?{urlencode(query)}"

    async def identify(self, code: str, verifier: str, device_id: str | None) -> SocialIdentity:
        """Exchange the code, then read the user and their verified addresses."""
        del device_id
        form = {
            "client_id": self._client_id, "client_secret": self._secret.get_secret_value(),
            "code": code, "code_verifier": verifier, "redirect_uri": self._redirect_uri,
        }  # fmt: skip
        try:
            response = await self._http.post(
                EXCHANGE_URL, data=form, headers={"Accept": "application/json"}
            )
            token = required(await json_object(response, "github: токен"), "access_token", "github")
            headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
            user = await json_object(await self._http.get(USER_URL, headers=headers), "github")
            emails = await self._http.get(EMAILS_URL, headers=headers)
        except httpx.HTTPError as error:
            message = "github: обмен кода не удался"
            raise SocialProviderFailedError(message) from error
        if emails.status_code != httpx.codes.OK:
            # GitHub App без разрешения «Email addresses: Read-only» отвечает 403.
            log.warning("GitHub не отдал адреса почты", status=emails.status_code)
        email = _verified_email(emails)
        return SocialIdentity(
            provider=self.key,
            subject=required(user, "id", "github"),
            email=email,
            email_verified=email is not None,
            display_name=text(user, "name") or text(user, "login"),
        )


def _verified_email(response: httpx.Response) -> str | None:
    if response.status_code != httpx.codes.OK:
        return None
    try:
        rows = response.json()
    except ValueError:
        return None
    if not isinstance(rows, list):
        return None
    verified = [
        (bool(row.get("primary")), row["email"].strip().lower())
        for row in rows
        if isinstance(row, dict)
        and row.get("verified") is True
        and isinstance(row.get("email"), str)
        and not row["email"].strip().lower().endswith(NO_REPLY)
    ]
    verified.sort(key=lambda pair: not pair[0])
    return verified[0][1] if verified else None
