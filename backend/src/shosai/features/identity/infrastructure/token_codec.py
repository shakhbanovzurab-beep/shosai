"""Signing and verifying tokens with the key ring (ADR 0045 point 1).

HS256 only, as the draft. The first key of the ring signs and names itself in the `kid`
header; every key verifies. A token without `kid` was signed by the draft and is checked
with the draft key alone. Every key is at least 32 bytes: the settings refuse a shorter
one, and PyJWT is told to enforce that rather than warn. A `kid` outside the ring,
another algorithm or a missing registered claim makes the token invalid. Verification
needs no clock skew allowance: every process signs and checks on the same plane.
"""

from collections.abc import Mapping
from typing import Final

import jwt

from shosai.features.identity.domain.tokens import (
    AccessClaims,
    InvalidTokenError,
    RefreshClaims,
    access_claims,
    access_payload,
    refresh_claims,
    refresh_payload,
)
from shosai.features.identity.settings import DRAFT_KEY_ID, TokenKey

ALGORITHM: Final = "HS256"
# Ключ короче 256 бит — ошибка, а не предупреждение на каждый запрос.
JWT: Final = jwt.PyJWT({"enforce_minimum_key_length": True})
REQUIRED_CLAIMS: Final = ("sub", "typ", "iat", "exp")


class TokenCodec:
    """Encodes claims into signed tokens and verified tokens back into claims."""

    def __init__(self, keys: tuple[TokenKey, ...]) -> None:
        if not keys:
            message = "кольцо ключей подписи пусто"
            raise ValueError(message)
        self._signing = keys[0]
        self._secrets: Mapping[str, str] = {
            key.key_id: key.secret.get_secret_value() for key in keys
        }

    def encode_access(self, claims: AccessClaims) -> str:
        """A signed access token."""
        return self._encode(access_payload(claims))

    def encode_refresh(self, claims: RefreshClaims) -> str:
        """A signed refresh token."""
        return self._encode(refresh_payload(claims))

    def decode_access(self, token: str) -> AccessClaims:
        """The claims of a valid, unexpired access token, or `InvalidTokenError`."""
        return access_claims(self._verify(token))

    def decode_refresh(self, token: str) -> RefreshClaims:
        """The claims of a valid, unexpired refresh token, or `InvalidTokenError`."""
        return refresh_claims(self._verify(token))

    def _encode(self, payload: dict[str, object]) -> str:
        return JWT.encode(
            payload,
            self._signing.secret.get_secret_value(),
            algorithm=ALGORITHM,
            headers={"kid": self._signing.key_id},
        )

    def _verify(self, token: str) -> dict[str, object]:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.InvalidTokenError as error:
            raise InvalidTokenError("malformed_token") from error
        key_id = header.get("kid", DRAFT_KEY_ID)
        secret = self._secrets.get(key_id) if isinstance(key_id, str) else None
        if secret is None:
            raise InvalidTokenError("unknown_key")
        try:
            payload: dict[str, object] = JWT.decode(
                token, secret, algorithms=[ALGORITHM], options={"require": list(REQUIRED_CLAIMS)}
            )
        except jwt.ExpiredSignatureError as error:
            raise InvalidTokenError("expired") from error
        except jwt.InvalidTokenError as error:
            raise InvalidTokenError("invalid_signature_or_claims") from error
        return payload
