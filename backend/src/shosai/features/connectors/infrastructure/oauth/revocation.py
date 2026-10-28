"""RFC 7009 token revocation, the common form most providers take (plan §3.5).

The token goes in the form with its type hint and the client authenticates as its
descriptor says. A token the provider no longer knows is revoked already; an outage or a
throttle is a failure the revocation task tries again.
"""

from typing import Final

import httpx
from pydantic import SecretStr

from shosai.features.connectors.domain.descriptors import ProviderDescriptor
from shosai.features.connectors.infrastructure.oauth.tokens import ClientCredentials, form_of
from shosai.features.connectors.infrastructure.providers.base import RevocationFailedError

HTTP_OK: Final = range(200, 300)
# Токен, которого провайдер уже не знает, — отозван (RFC 7009 §2.2).
ALREADY_GONE: Final = frozenset({400, 401, 404})


async def revoke_by_form(
    http: httpx.AsyncClient,
    descriptor: ProviderDescriptor,
    credentials: ClientCredentials,
    token: tuple[SecretStr, str],
) -> None:
    """POST the token to the provider's revocation endpoint."""
    url = descriptor.revocation.url
    if url is None:
        return
    value, hint = token
    fields, auth = form_of(
        descriptor, credentials, {"token": value.get_secret_value(), "token_type_hint": hint}
    )
    timeout = httpx.Timeout(
        descriptor.timeouts.token.total_seconds(),
        connect=descriptor.timeouts.connect.total_seconds(),
    )
    try:
        response = await http.post(
            url, data=fields, auth=auth or httpx.USE_CLIENT_DEFAULT, timeout=timeout
        )
    except httpx.HTTPError:
        raise RevocationFailedError from None
    if response.status_code not in HTTP_OK and response.status_code not in ALREADY_GONE:
        raise RevocationFailedError
