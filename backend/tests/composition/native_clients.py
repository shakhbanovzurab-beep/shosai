"""How the shipped macOS and Windows 1.4.5 clients decode identity's answers (identity step 13).

Each check mirrors the clients' DTOs field by field — `AuthClient.swift` in WhispererKit and
`AuthClient.cs` in the Windows client, as `contracts/draft/consumers.json` points to them. A
field a client requires must be present with its type; an optional one may be missing or
null but never of another type, since one wrong value fails the decoding of the whole body.
"""

from collections.abc import Mapping
from typing import Final

type Body = Mapping[str, object]

# Целое у клиентов — int в Swift и C#: true и false им не подходят, хотя в Python это int.
INTEGER: Final = (int,)
NUMBER: Final = (int, float)


def _typed(name: str, value: object, kinds: tuple[type, ...]) -> object:
    if bool not in kinds:
        assert not isinstance(value, bool), (name, value)
    assert isinstance(value, kinds), (name, value)
    return value


def _required(body: Body, name: str, kinds: tuple[type, ...]) -> object:
    value = body.get(name)
    assert value is not None, (name, body)
    return _typed(name, value, kinds)


def _optional(body: Body, name: str, kinds: tuple[type, ...]) -> object:
    value = body.get(name)
    return None if value is None else _typed(name, value, kinds)


def decode_token_response(body: Body) -> str:
    """`AuthTokenResponse` of `/auth/login` and `/auth/refresh`; the access token."""
    _required(body, "token_type", (str,))
    _required(body, "expires_in", INTEGER)
    _optional(body, "csrf_token", (str,))
    return str(_required(body, "access_token", (str,)))


def decode_desktop_tokens(body: Body) -> tuple[str, str]:
    """`DesktopTokenResponse` of the desktop exchange and refresh; access and refresh tokens."""
    _required(body, "expires_in", INTEGER)
    access = _required(body, "access_token", (str,))
    refresh = _required(body, "refresh_token", (str,))
    return str(access), str(refresh)


def decode_auth_user(body: Body) -> str:
    """`AuthUser` of `/auth/me`: email and role are required on both clients; the email."""
    _required(body, "role", (str,))
    _optional(body, "language", (str,))
    _optional(body, "no_logs", (bool,))
    subscription = _optional(body, "subscription", (dict,))
    if isinstance(subscription, dict):
        _required(subscription, "status", (str,))
        _optional(subscription, "days_left", INTEGER)
        tariff = _optional(subscription, "tariff", (dict,))
        if isinstance(tariff, dict):
            _required(tariff, "code", (str,))
            _required(tariff, "name", (str,))
            _optional(tariff, "minutes_limit", INTEGER)
    quota = _optional(body, "quota", (dict,))
    if isinstance(quota, dict):
        _required(quota, "unlimited", (bool,))
        _required(quota, "exhausted", (bool,))
        _optional(quota, "remaining_minutes", NUMBER)
    features = _optional(body, "features", (dict,))
    if isinstance(features, dict):
        _required(features, "voice_translation", (bool,))
        _optional(features, "teleprompter", (bool,))
    return str(_required(body, "email", (str,)))
