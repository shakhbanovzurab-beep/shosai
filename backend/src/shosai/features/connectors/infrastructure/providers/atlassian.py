"""Atlassian OAuth 2.0 (3LO): the Jira grant, and Confluence's on the same consent (CN-D9).

Atlassian's token endpoint takes JSON, the authorize URL must carry
`audience=api.atlassian.com` (without it every Jira call answers 401) and `prompt=consent`
(without it a reconnect returns a grant without a refresh token, which lives an hour). The
refresh token rotates and is single use: the core stores every new one under its lease; a
reused one is refused with `unauthorized_client`, which breaks the grant. A refresh token
unused for 90 days dies, so the grant is kept alive. Atlassian has no revocation for 3LO
applications: a disconnect only forgets, and the person removes the app in their account.

The account is `/me`; the sites the person granted (each `cloud_id` addresses Jira's and
Confluence's APIs) are `accessible-resources`, kept in the grant's `provider_meta` with the
moment the profile was read — the personal data report names it (plan §3.5).
"""

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Final

import httpx

from shosai.features.connectors.domain.catalogue import Provider
from shosai.features.connectors.domain.descriptors import (
    LimitSubject,
    ProviderDescriptor,
    ProviderLimit,
    Revocation,
    RevocationKind,
    TokenAuth,
)
from shosai.features.connectors.domain.flows import FlowError
from shosai.features.connectors.infrastructure.oauth.tokens import (
    ClientCredentials,
    TokenSet,
    standard_tokens,
)
from shosai.features.connectors.infrastructure.providers.base import (
    AccountIdentity,
    HeldTokens,
    ProviderAnswerError,
)

API: Final = "https://api.atlassian.com"
AUTH: Final = "https://auth.atlassian.com"
ME_URL: Final = f"{API}/me"
SITES_URL: Final = f"{API}/oauth/token/accessible-resources"
ATLASSIAN: Final = ProviderDescriptor(
    provider=Provider.ATLASSIAN, client_key="atlassian",
    authorize_url=f"{AUTH}/authorize", token_url=f"{AUTH}/oauth/token", token_auth=TokenAuth.JSON,
    pkce=True,
    revocation=Revocation(RevocationKind.NONE),
    authorize_params=(("audience", "api.atlassian.com"), ("prompt", "consent")),
    rotating_refresh=True, idle_expiry=timedelta(days=90), union_scopes=True,
    # Квота Atlassian — 65 000 очков в час на приложение; вызов стоит не меньше очка.
    limits=(ProviderLimit("points", LimitSubject.APPLICATION, 65_000, timedelta(hours=1), 500),),
    concurrency_per_account=8,
    redirect_path="/v1/jira/oauth/callback",
)  # fmt: skip


def sites_of(answer: object) -> list[dict[str, str]]:
    """The granted sites of an `accessible-resources` answer, by `cloud_id`."""
    if not isinstance(answer, list):
        message = "accessible-resources ответил не списком"
        raise ProviderAnswerError(message)
    sites: list[dict[str, str]] = []
    for item in answer:
        if isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"]:
            name, url = item.get("name"), item.get("url")
            sites.append({
                "cloud_id": item["id"], "name": name if isinstance(name, str) else "",
                "url": url if isinstance(url, str) else "",
            })  # fmt: skip
    return sites


async def read_profile(http: httpx.AsyncClient, access_token: str) -> AccountIdentity:
    """The account of a token and its sites; `profile_at` is when they were read."""
    headers = {"Authorization": f"Bearer {access_token}"}
    me = await http.get(ME_URL, headers=headers)
    me.raise_for_status()
    sites = await http.get(SITES_URL, headers=headers)
    sites.raise_for_status()
    try:
        profile, granted = me.json(), sites.json()
    except ValueError:
        message = "Atlassian ответил не JSON"
        raise ProviderAnswerError(message) from None
    account_id = profile.get("account_id") if isinstance(profile, dict) else None
    if not isinstance(account_id, str) or not account_id:
        message = "/me без account_id"
        raise ProviderAnswerError(message)
    label = profile.get("email") or profile.get("name")
    meta = {"sites": sites_of(granted), "profile_at": datetime.now(UTC).isoformat()}
    return AccountIdentity(account_id, label if isinstance(label, str) else None, meta)


class AtlassianAdapter:
    """The Jira and Confluence application of Atlassian's developer console."""

    @property
    def descriptor(self) -> ProviderDescriptor:
        """Atlassian's endpoints and rules."""
        return ATLASSIAN

    def tokens(self, payload: Mapping[str, object], now: datetime) -> TokenSet:
        """The standard fields; the new refresh token replaces the old one every time."""
        return standard_tokens(payload, now)

    async def identify(self, http: httpx.AsyncClient, tokens: TokenSet) -> AccountIdentity:
        """The Atlassian account and its granted sites."""
        return await read_profile(http, tokens.access_token.get_secret_value())

    def callback_error(self, error: str, description: str | None) -> FlowError | None:
        """Atlassian names no error of its own beyond RFC 6749's."""
        del error, description
        return None

    async def revoke(
        self, http: httpx.AsyncClient, credentials: ClientCredentials, tokens: HeldTokens
    ) -> None:
        """Atlassian has no revocation for 3LO applications: the grant is only forgotten."""
        del http, credentials, tokens
