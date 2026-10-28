"""A provider's token endpoint: the code exchange and the refresh (RFC 6749 §4.1.3, §6).

The client proves itself the way its descriptor says — the secret in the form, HTTP Basic,
or a JSON body (Atlassian, Notion) — and sends the PKCE verifier when the flow had one. An
answer is a `TokenSet` or a `TokenEndpointError` that carries the class of the answer
(`classify_refresh`), so a caller never reads a provider's error text. Tokens stay
`SecretStr` until they are encrypted: no log, span or exception ever holds one.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Final

import httpx
from pydantic import SecretStr

from shosai.features.connectors.domain.descriptors import ProviderDescriptor, TokenAuth
from shosai.features.connectors.domain.refresh import RefreshOutcome, classify_refresh
from shosai.features.connectors.domain.scopes import parse_scope

JSON_BODIES: Final = frozenset({TokenAuth.JSON, TokenAuth.BASIC_JSON})
BASIC_AUTH: Final = frozenset({TokenAuth.BASIC, TokenAuth.BASIC_JSON})


@dataclass(frozen=True, slots=True)
class ClientCredentials:
    """One OAuth application's id and secret; a public client has no secret."""

    client_id: str
    client_secret: SecretStr | None = None


@dataclass(frozen=True, slots=True)
class TokenSet:
    """What a token endpoint gave: secrets stay wrapped."""

    access_token: SecretStr
    refresh_token: SecretStr | None
    expires_at: datetime | None
    # None — провайдер не назвал права в ответе: остаются запрошенные.
    scopes: frozenset[str] | None
    # Ответ целиком для адаптера провайдера (Slack кладёт токен человека в authed_user).
    payload: Mapping[str, object] = field(repr=False, default_factory=dict)


class TokenEndpointError(Exception):
    """The token endpoint did not give tokens; `outcome` says what that means."""

    def __init__(self, outcome: RefreshOutcome, status: int | None, code: str | None) -> None:
        super().__init__(f"конечная точка токенов: {outcome} (статус {status}, код {code})")
        self.outcome = outcome
        self.status = status
        self.code = code


def standard_tokens(payload: Mapping[str, object], now: datetime, separator: str = " ") -> TokenSet:
    """The RFC 6749 §5.1 fields of a successful answer."""
    access = payload.get("access_token")
    if not isinstance(access, str) or not access:
        raise TokenEndpointError(RefreshOutcome.TRANSIENT, None, "no_access_token")
    refresh = payload.get("refresh_token")
    expires_in = payload.get("expires_in")
    expires_at = None
    if isinstance(expires_in, int | float | str) and str(expires_in).isdigit():
        expires_at = now + timedelta(seconds=int(expires_in))
    scope = payload.get("scope")
    return TokenSet(
        access_token=SecretStr(access),
        refresh_token=SecretStr(refresh) if isinstance(refresh, str) and refresh else None,
        expires_at=expires_at,
        scopes=parse_scope(scope, separator) if isinstance(scope, str) else None,
        payload=payload,
    )


def form_of(
    descriptor: ProviderDescriptor, credentials: ClientCredentials, form: dict[str, str]
) -> tuple[dict[str, str], httpx.BasicAuth | None]:
    """The token request's fields and its HTTP Basic auth, by the descriptor's method."""
    secret = credentials.client_secret.get_secret_value() if credentials.client_secret else None
    if descriptor.token_auth in BASIC_AUTH and secret is not None:
        return form, httpx.BasicAuth(credentials.client_id, secret)
    fields = {**form, "client_id": credentials.client_id}
    if secret is not None:
        fields["client_secret"] = secret
    return fields, None


async def post_token_request(
    http: httpx.AsyncClient,
    descriptor: ProviderDescriptor,
    credentials: ClientCredentials,
    form: dict[str, str],
) -> Mapping[str, object]:
    """One call to the token endpoint; the JSON of a success, else `TokenEndpointError`."""
    fields, auth = form_of(descriptor, credentials, form)
    timeout = httpx.Timeout(
        descriptor.timeouts.token.total_seconds(),
        connect=descriptor.timeouts.connect.total_seconds(),
    )
    headers = {"Accept": "application/json"}
    try:
        if descriptor.token_auth in JSON_BODIES:
            response = await http.post(
                descriptor.token_url,
                json=fields,
                headers=headers,
                auth=auth or httpx.USE_CLIENT_DEFAULT,
                timeout=timeout,
            )
        else:
            response = await http.post(
                descriptor.token_url,
                data=fields,
                headers=headers,
                auth=auth or httpx.USE_CLIENT_DEFAULT,
                timeout=timeout,
            )
    except httpx.HTTPError:
        raise TokenEndpointError(RefreshOutcome.TRANSIENT, None, None) from None
    return answer_of(response)


def answer_of(response: httpx.Response) -> Mapping[str, object]:
    """The JSON of a successful token answer, else `TokenEndpointError` with its class."""
    try:
        payload = response.json()
    except ValueError:
        payload = None
    if not isinstance(payload, dict):
        outcome = classify_refresh(response.status_code, None)
        failed = RefreshOutcome.TRANSIENT if outcome is RefreshOutcome.REFRESHED else outcome
        raise TokenEndpointError(failed, response.status_code, "not_json")
    error = payload.get("error")
    code = error if isinstance(error, str) else None
    # Slack отвечает 200 с ok: false и кодом в error.
    if payload.get("ok") is False and code is None:
        code = "not_ok"
    outcome = classify_refresh(response.status_code, code)
    if outcome is not RefreshOutcome.REFRESHED:
        raise TokenEndpointError(outcome, response.status_code, code)
    return payload


@dataclass(frozen=True, slots=True)
class TokenEndpoint:
    """The code exchange and the refresh of one OAuth application."""

    http: httpx.AsyncClient
    descriptor: ProviderDescriptor
    credentials: ClientCredentials

    async def exchange(
        self, code: str, redirect_uri: str, verifier: str | None
    ) -> Mapping[str, object]:
        """The answer to an authorization code."""
        form = {"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri}
        if verifier is not None and self.descriptor.pkce:
            form["code_verifier"] = verifier
        return await post_token_request(self.http, self.descriptor, self.credentials, form)

    async def refresh(self, refresh_token: SecretStr) -> Mapping[str, object]:
        """The answer to a refresh token."""
        form = {"grant_type": "refresh_token", "refresh_token": refresh_token.get_secret_value()}
        return await post_token_request(self.http, self.descriptor, self.credentials, form)
