"""The claims of access and refresh tokens, compatible with the draft (DATA_MAPPING R6).

The draft signs `sub` (the user id), `typ`, `tv` (the token version, 0 when absent),
`iat` and `exp`; refresh tokens add `fid` (the session family) and `jti`. v2 keeps every
claim, so tokens issued before the cutover stay valid, and adds `home`. A draft token has
no `home`: identity resolves it through the directory for the ≤ 30 minutes such access
tokens live. Encoding and signatures are infrastructure; this module only turns a
verified payload into claims and claims into a payload.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Final
from uuid import UUID

from shosai.core.kernel.homes import Home

ACCESS_TOKEN_LIFETIME: Final = timedelta(minutes=30)
REFRESH_TOKEN_LIFETIME: Final = timedelta(days=7)


class TokenKind(StrEnum):
    """The `typ` claim: a refresh token never opens a request, an access token never refreshes."""

    ACCESS = "access"
    REFRESH = "refresh"


class InvalidTokenError(Exception):
    """The token cannot be used; the reason is a code for logs, never shown to the client."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True, slots=True)
class AccessClaims:
    """Who a request acts for."""

    user_id: UUID
    # None — токен черновика: дом ищется в каталоге.
    home: Home | None
    token_version: int
    issued_at: datetime
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class RefreshClaims:
    """Which session family a refresh token belongs to, and which of its tokens it is."""

    user_id: UUID
    home: Home | None
    token_version: int
    family_id: UUID
    token_id: str
    issued_at: datetime
    expires_at: datetime


def access_payload(claims: AccessClaims) -> dict[str, object]:
    """The JWT payload of an access token."""
    return _common_payload(TokenKind.ACCESS, claims)


def refresh_payload(claims: RefreshClaims) -> dict[str, object]:
    """The JWT payload of a refresh token."""
    payload = _common_payload(TokenKind.REFRESH, claims)
    payload["fid"] = str(claims.family_id)
    payload["jti"] = claims.token_id
    return payload


def access_claims(payload: Mapping[str, object]) -> AccessClaims:
    """The claims of a verified access token, or `InvalidTokenError`."""
    _expect_kind(payload, TokenKind.ACCESS)
    return AccessClaims(
        user_id=_uuid(payload, "sub"),
        home=_home(payload),
        token_version=_token_version(payload),
        issued_at=_time(payload, "iat"),
        expires_at=_time(payload, "exp"),
    )


def refresh_claims(payload: Mapping[str, object]) -> RefreshClaims:
    """The claims of a verified refresh token, or `InvalidTokenError`."""
    _expect_kind(payload, TokenKind.REFRESH)
    token_id = payload.get("jti")
    if not isinstance(token_id, str) or not token_id:
        raise InvalidTokenError("refresh_without_jti")
    return RefreshClaims(
        user_id=_uuid(payload, "sub"),
        home=_home(payload),
        token_version=_token_version(payload),
        family_id=_uuid(payload, "fid"),
        token_id=token_id,
        issued_at=_time(payload, "iat"),
        expires_at=_time(payload, "exp"),
    )


def _common_payload(kind: TokenKind, claims: AccessClaims | RefreshClaims) -> dict[str, object]:
    payload: dict[str, object] = {
        "sub": str(claims.user_id),
        "typ": kind.value,
        "tv": claims.token_version,
        "iat": int(claims.issued_at.timestamp()),
        "exp": int(claims.expires_at.timestamp()),
    }
    if claims.home is not None:
        payload["home"] = claims.home.value
    return payload


def _expect_kind(payload: Mapping[str, object], kind: TokenKind) -> None:
    if payload.get("typ") != kind.value:
        raise InvalidTokenError("wrong_token_kind")


def _uuid(payload: Mapping[str, object], claim: str) -> UUID:
    value = payload.get(claim)
    if not isinstance(value, str):
        raise InvalidTokenError(f"missing_{claim}")
    try:
        return UUID(value)
    except ValueError as error:
        raise InvalidTokenError(f"malformed_{claim}") from error


def _home(payload: Mapping[str, object]) -> Home | None:
    value = payload.get("home")
    if value is None:
        return None
    if not isinstance(value, str) or value not in Home:
        raise InvalidTokenError("unknown_home")
    return Home(value)


def _token_version(payload: Mapping[str, object]) -> int:
    # Токены черновика старше счётчика версий не несут tv: это версия 0 (как у черновика).
    value = payload.get("tv", 0)
    if type(value) is not int or value < 0:
        raise InvalidTokenError("malformed_tv")
    return value


def _time(payload: Mapping[str, object], claim: str) -> datetime:
    value = payload.get(claim)
    if type(value) is not int:
        raise InvalidTokenError(f"malformed_{claim}")
    return datetime.fromtimestamp(value, UTC)
