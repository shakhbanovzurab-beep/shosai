"""Refresh families: rotation, the double-refresh grace and reuse detection (ADR 0045 point 1).

A family is one signed-in device; each refresh rotates its token. The token id (`jti`) of
generation N is HMAC(key, family:N), so the server stores only SHA-256 of the current and
previous ids (spec 022) yet can sign the current token again: when two tabs refresh at
once, the second presents the previous id within 10 seconds and gets the current token,
not a new rotation that would sign the first tab out (draft commit 18ab7bf67). Any other
old id is a stolen token being replayed, and the whole family is revoked.
"""

import hashlib
import hmac
import secrets
from base64 import urlsafe_b64encode
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Final
from uuid import UUID

REFRESH_GRACE: Final = timedelta(seconds=10)
CSRF_TOKEN_BYTES: Final = 32
TOKEN_ID_BYTES: Final = 24


class ClientKind(StrEnum):
    """Where a family lives: a browser (cookies) or a desktop app (tokens in the body)."""

    WEB = "web"
    DESKTOP = "desktop"


class RotationVerdict(StrEnum):
    """What a presented refresh token means for its family."""

    ROTATE = "rotate"
    # Повтор в окне 10 с: вернуть текущий токен, ничего не вращая.
    GRACE = "grace"
    # Старый токен вне окна — кража: отозвать семейство целиком.
    REUSE = "reuse"
    EXPIRED = "expired"
    REVOKED = "revoked"


@dataclass(frozen=True, slots=True)
class FamilyState:
    """What the server keeps of a family to judge a refresh."""

    current_id_hash: bytes
    previous_id_hash: bytes | None
    rotated_at: datetime | None
    expires_at: datetime
    revoked: bool


def token_id(key: bytes, family_id: UUID, generation: int) -> str:
    """The token id of a family's generation: reproducible only with the key."""
    digest = hmac.new(key, f"{family_id}:{generation}".encode("ascii"), hashlib.sha256)
    return urlsafe_b64encode(digest.digest()[:TOKEN_ID_BYTES]).decode("ascii")


def token_id_hash(value: str) -> bytes:
    """SHA-256 of a token id, as the family row stores it."""
    return hashlib.sha256(value.encode("ascii", "replace")).digest()


def judge(family: FamilyState, presented_id: str, now: datetime) -> RotationVerdict:
    """The verdict on a refresh with the presented token id."""
    if family.revoked:
        return RotationVerdict.REVOKED
    if family.expires_at <= now:
        return RotationVerdict.EXPIRED
    presented = token_id_hash(presented_id)
    if secrets.compare_digest(presented, family.current_id_hash):
        return RotationVerdict.ROTATE
    in_grace = family.rotated_at is not None and now - family.rotated_at <= REFRESH_GRACE
    previous = family.previous_id_hash
    if in_grace and previous is not None and secrets.compare_digest(presented, previous):
        return RotationVerdict.GRACE
    return RotationVerdict.REUSE


def new_csrf_token() -> str:
    """The value of the CSRF cookie and header pair (double submit)."""
    return secrets.token_urlsafe(CSRF_TOKEN_BYTES)


def csrf_matches(cookie: str | None, header: str | None) -> bool:
    """Whether the header repeats the cookie, compared in constant time."""
    if not cookie or not header:
        return False
    return secrets.compare_digest(cookie.encode("utf-8"), header.encode("utf-8"))
