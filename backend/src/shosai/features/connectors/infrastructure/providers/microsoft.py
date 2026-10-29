"""Microsoft Entra: one multi-tenant application (`common`) for Outlook mail and calendar (plan
step 13).

`prompt=select_account` lets a person choose between a work and a personal account. A work
tenant may require its admin's approval: Entra answers the callback with AADSTS65001 or
AADSTS90094 (or `consent_required`), which the cabinet words as `admin_consent_required`. The
refresh token is replaced at every refresh and dies after 90 days unused, so the core stores
each new one and keeps the grant alive. Microsoft has no revocation for an application's
tokens: a disconnect only forgets, and the person removes the app in their account. The
account is Graph's `/me`; the tenant comes from the ID token's `tid`, read without trusting
it for anything but a label, since the token came straight from Entra over TLS.
"""

import base64
import json
from collections.abc import Mapping
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Final

import httpx

from shosai.features.connectors.domain.catalogue import Provider, apps_of, spec_of
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

LOGIN: Final = "https://login.microsoftonline.com/common/oauth2/v2.0"
ME_URL: Final = "https://graph.microsoft.com/v1.0/me?$select=id,mail,userPrincipalName,displayName"
JWT_PARTS: Final = 3
GRAPH_SCOPE: Final = "https://graph.microsoft.com/"
OPENID: Final = frozenset({"openid", "email", "profile"})
# Коды Entra, которыми тенант говорит «нужно согласие администратора».
ADMIN_CODES: Final = ("AADSTS65001", "AADSTS90094", "AADSTS90008")
MICROSOFT: Final = ProviderDescriptor(
    provider=Provider.MICROSOFT, client_key="microsoft", authorize_url=f"{LOGIN}/authorize",
    token_url=f"{LOGIN}/token", token_auth=TokenAuth.BODY, pkce=True,
    revocation=Revocation(RevocationKind.NONE), authorize_params=(("prompt", "select_account"),),
    rotating_refresh=True, idle_expiry=timedelta(days=90), union_scopes=True,
    # Outlook: 10 000 запросов за 10 минут и не больше 4 одновременно на ящик.
    limits=(ProviderLimit("calls", LimitSubject.ACCOUNT, 10_000, timedelta(minutes=10), 500),),
    concurrency_per_account=4,
)  # fmt: skip


def graph_scopes(tokens: TokenSet) -> frozenset[str] | None:
    """Entra's granted scopes as the catalogue names them.

    Entra names Graph's scopes by their full address, in any case, and never lists
    `offline_access` or the OpenID scopes: a refresh token means the first, an ID token the rest.
    """
    if tokens.scopes is None:
        return None
    named = {
        scope.lower(): scope for app in apps_of(Provider.MICROSOFT) for scope in spec_of(app).scopes
    }
    granted = {named.get(scope.removeprefix(GRAPH_SCOPE).lower(), scope) for scope in tokens.scopes}
    if tokens.refresh_token is not None:
        granted.add("offline_access")
    if isinstance(tokens.payload.get("id_token"), str):
        granted |= OPENID
    return frozenset(granted)


def tenant_of(id_token: object) -> str | None:
    """The `tid` claim of an ID token, or None when there is none to read."""
    if not isinstance(id_token, str) or len(id_token.split(".")) != JWT_PARTS:
        return None
    payload = id_token.split(".")[1]
    try:
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except ValueError:
        return None
    tenant = claims.get("tid") if isinstance(claims, dict) else None
    return tenant if isinstance(tenant, str) else None


class MicrosoftAdapter:
    """The Entra application of Outlook mail and calendar."""

    @property
    def descriptor(self) -> ProviderDescriptor:
        """Entra's endpoints and rules."""
        return MICROSOFT

    def tokens(self, payload: Mapping[str, object], now: datetime) -> TokenSet:
        """The standard fields with the scopes as the catalogue names them."""
        tokens = standard_tokens(payload, now)
        return replace(tokens, scopes=graph_scopes(tokens))

    async def identify(self, http: httpx.AsyncClient, tokens: TokenSet) -> AccountIdentity:
        """The Microsoft account, its address, and its tenant."""
        answer = await http.get(
            ME_URL, headers={"Authorization": f"Bearer {tokens.access_token.get_secret_value()}"}
        )
        answer.raise_for_status()
        try:
            profile = answer.json()
        except ValueError:
            message = "Graph /me ответил не JSON"
            raise ProviderAnswerError(message) from None
        account = profile.get("id") if isinstance(profile, dict) else None
        if not isinstance(account, str) or not account:
            message = "Graph /me без id"
            raise ProviderAnswerError(message)
        label = profile.get("mail") or profile.get("userPrincipalName")
        tenant = tenant_of(tokens.payload.get("id_token"))
        return AccountIdentity(
            account, label if isinstance(label, str) else None, {"tenant": tenant} if tenant else {}
        )

    def callback_error(self, error: str, description: str | None) -> FlowError | None:
        """A tenant that needs its admin's approval first."""
        if error == "consent_required" or any(code in (description or "") for code in ADMIN_CODES):
            return FlowError.ADMIN_CONSENT_REQUIRED
        return None

    async def revoke(
        self, http: httpx.AsyncClient, credentials: ClientCredentials, tokens: HeldTokens
    ) -> None:
        """Microsoft has no revocation for an application's tokens: the grant is only forgotten."""
        del http, credentials, tokens
