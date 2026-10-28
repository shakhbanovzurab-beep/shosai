"""Google: two OAuth applications in two Cloud projects (CN-D5).

The main project (`google`) holds Calendar and Drive on one grant per account: a second app
asks only for its own scopes, `include_granted_scopes=true` makes the token cover both, and
the answer names every scope granted — Google's consent screen lets a person untick a box,
so each app is checked for its own. "Shosai Mail" (`google_mail`) holds Gmail alone, so its
restricted scope stays in a project of its own. `access_type=offline` with `prompt=consent`
gives a refresh token at every consent; it does not rotate and dies after six months unused.
A project in Google's Testing status gives refresh tokens that live seven days whatever is
done with them; the deployment says which projects are in Testing.

Revocation takes the refresh token and removes every scope of the whole project for that
person, which is why the core revokes a grant only when its last app is gone. The account is
OpenID Connect's `userinfo`: its `sub` is the stable id, its email the label. Google names
the `email` scope `userinfo.email` in the token answer; the adapter reads it back as `email`.
"""

from collections.abc import Mapping
from dataclasses import dataclass, replace
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
from shosai.features.connectors.infrastructure.oauth.revocation import revoke_by_form
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

USERINFO_URL: Final = "https://openidconnect.googleapis.com/v1/userinfo"
OAUTH_HOST: Final = "https://oauth2.googleapis.com"
TESTING_LIFETIME: Final = timedelta(days=7)
# Как Google называет в ответе права OpenID, которые запрашиваются короткими именами.
OPENID_ALIASES: Final = {
    "https://www.googleapis.com/auth/userinfo.email": "email",
    "https://www.googleapis.com/auth/userinfo.profile": "profile",
}
CALLBACK_ERRORS: Final = {
    "admin_policy_enforced": FlowError.ADMIN_CONSENT_REQUIRED,
    "org_internal": FlowError.NOT_OFFERED,
}
GOOGLE: Final = ProviderDescriptor(
    provider=Provider.GOOGLE, client_key="google",
    authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
    token_url=f"{OAUTH_HOST}/token", token_auth=TokenAuth.BODY, pkce=True,
    revocation=Revocation(RevocationKind.REFRESH, f"{OAUTH_HOST}/revoke"),
    authorize_params=(
        ("access_type", "offline"), ("include_granted_scopes", "true"), ("prompt", "consent"),
    ),
    idle_expiry=timedelta(days=182), reports_granted_scopes=True,
    # Calendar — 600 запросов в минуту на человека; Drive щедрее, предел общий для проекта.
    limits=(ProviderLimit("calls", LimitSubject.ACCOUNT, 600, timedelta(minutes=1), 100),),
)  # fmt: skip
GOOGLE_MAIL: Final = replace(GOOGLE, client_key="google_mail", limits=())


def openid_scopes(scopes: frozenset[str] | None) -> frozenset[str] | None:
    """The granted scopes with OpenID's long names read back as the short ones asked for."""
    if scopes is None:
        return None
    return frozenset(OPENID_ALIASES.get(scope, scope) for scope in scopes)


@dataclass(frozen=True, slots=True)
class GoogleAdapter:
    """One of Google's two applications."""

    descriptor: ProviderDescriptor

    def tokens(self, payload: Mapping[str, object], now: datetime) -> TokenSet:
        """The standard fields, with the scopes as the catalogue names them."""
        tokens = standard_tokens(payload, now)
        return replace(tokens, scopes=openid_scopes(tokens.scopes))

    async def identify(self, http: httpx.AsyncClient, tokens: TokenSet) -> AccountIdentity:
        """The Google account; `consent_at` dates the refresh token for a Testing project."""
        answer = await http.get(
            USERINFO_URL,
            headers={"Authorization": f"Bearer {tokens.access_token.get_secret_value()}"},
        )
        answer.raise_for_status()
        try:
            profile = answer.json()
        except ValueError:
            message = "userinfo Google ответил не JSON"
            raise ProviderAnswerError(message) from None
        subject = profile.get("sub") if isinstance(profile, dict) else None
        if not isinstance(subject, str) or not subject:
            message = "userinfo Google без sub"
            raise ProviderAnswerError(message)
        email = profile.get("email")
        meta = {"consent_at": datetime.now(UTC).isoformat()}
        return AccountIdentity(subject, email if isinstance(email, str) else None, meta)

    def callback_error(self, error: str, description: str | None) -> FlowError | None:
        """A Workspace admin's block, or an app restricted to its own organisation."""
        del description
        return CALLBACK_ERRORS.get(error)

    async def revoke(
        self, http: httpx.AsyncClient, credentials: ClientCredentials, tokens: HeldTokens
    ) -> None:
        """Revoke with the refresh token: the whole project's scopes go for this person."""
        token = tokens.refresh_token or tokens.access_token
        if token is None:
            return
        hint = "refresh_token" if tokens.refresh_token is not None else "access_token"
        await revoke_by_form(http, self.descriptor, credentials, (token, hint))
