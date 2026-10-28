"""The addresses of a connect flow: the provider's authorize URL and Shosai's callback.

The callback is `/v1/connectors/oauth/<provider>/callback` on Shosai's public address, the
redirect URI each OAuth application registers; both Google applications of CN-D5 share
Google's. A provider whose application registered another path names it in its descriptor:
Atlassian keeps the draft's `/v1/jira/oauth/callback`. The authorize URL names the client,
the callback, the one-time state, the scopes in the provider's separator, the S256
challenge where the provider takes PKCE, and the descriptor's own parameters, which never
override these.
"""

from collections.abc import Collection
from dataclasses import dataclass
from urllib.parse import urlencode, urlsplit

from shosai.features.connectors.domain.descriptors import ProviderDescriptor
from shosai.features.connectors.domain.flows import challenge_of


def callback_uri(base_url: str, descriptor: ProviderDescriptor) -> str:
    """The redirect URI registered with the provider."""
    path = descriptor.redirect_path or f"/v1/connectors/oauth/{descriptor.provider.value}/callback"
    return f"{base_url.rstrip('/')}{path}"


@dataclass(frozen=True, slots=True)
class AuthorizeQuery:
    """What one flow puts into the provider's authorize URL."""

    client_id: str
    redirect_uri: str
    state: str
    scopes: Collection[str]
    verifier: str
    login_hint: str | None = None


def authorize_url(descriptor: ProviderDescriptor, flow: AuthorizeQuery) -> str:
    """Where the popup goes to consent at the provider."""
    query: dict[str, str] = dict(descriptor.authorize_params)
    query |= {"response_type": "code", "client_id": flow.client_id,
              "redirect_uri": flow.redirect_uri, "state": flow.state}  # fmt: skip
    if flow.scopes:
        query["scope"] = descriptor.scope_separator.join(sorted(flow.scopes))
    if descriptor.pkce:
        query |= {"code_challenge": challenge_of(flow.verifier), "code_challenge_method": "S256"}
    if flow.login_hint is not None:
        query["login_hint"] = flow.login_hint
    separator = "&" if urlsplit(descriptor.authorize_url).query else "?"
    return f"{descriptor.authorize_url}{separator}{urlencode(query)}"
