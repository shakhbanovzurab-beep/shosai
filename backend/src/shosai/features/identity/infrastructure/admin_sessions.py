"""Sessions of the one admin (ADR 0049): a signed nonce in a cookie, its hash in Valkey.

The cookie carries a random nonce and its HMAC under a key derived from the token signing
key, so a forged cookie fails before Valkey is asked. Valkey keeps the nonce's hash for the
session's life: signing out deletes it and the cookie stops working at once, everywhere.
Nothing about people is stored — the admin is not a person's account.
"""

import asyncio
import base64
import hashlib
import hmac
import secrets
from datetime import timedelta
from typing import Final

from redis.asyncio import Redis

from shosai.core.kv.connection import REDIS_FAILURES
from shosai.core.kv.keys import build_key

ADMIN_SESSION_LIFETIME: Final = timedelta(hours=8)
DERIVATION: Final = b"shosai.identity.admin_session.v1"
NONCE_BYTES: Final = 32
SEPARATOR: Final = "."
DEADLINE: Final = timedelta(milliseconds=200)


class AdminSessionsUnavailableError(Exception):
    """Valkey did not answer: no admin session can be opened or checked now."""


class AdminSessions:
    """Open, check and close admin sessions."""

    def __init__(self, valkey: Redis, signing_key: bytes) -> None:
        self._valkey = valkey
        self._key = hashlib.sha256(DERIVATION + signing_key).digest()

    async def open(self) -> str:
        """A new session; the value of the admin cookie."""
        nonce = _encode(secrets.token_bytes(NONCE_BYTES))
        try:
            async with asyncio.timeout(DEADLINE.total_seconds()):
                await self._valkey.set(
                    _record(nonce), "1", ex=int(ADMIN_SESSION_LIFETIME.total_seconds())
                )
        except REDIS_FAILURES as error:
            raise AdminSessionsUnavailableError from error
        return f"{nonce}{SEPARATOR}{self._mac(nonce)}"

    async def valid(self, cookie: str | None) -> bool:
        """Whether the cookie belongs to a live session this server opened."""
        nonce = self._nonce(cookie)
        if nonce is None:
            return False
        try:
            async with asyncio.timeout(DEADLINE.total_seconds()):
                return bool(await self._valkey.exists(_record(nonce)))
        except REDIS_FAILURES as error:
            raise AdminSessionsUnavailableError from error

    async def close(self, cookie: str | None) -> None:
        """End the session of the cookie; an unknown cookie changes nothing."""
        nonce = self._nonce(cookie)
        if nonce is None:
            return
        try:
            async with asyncio.timeout(DEADLINE.total_seconds()):
                await self._valkey.delete(_record(nonce))
        except REDIS_FAILURES as error:
            raise AdminSessionsUnavailableError from error

    def _nonce(self, cookie: str | None) -> str | None:
        if not cookie or not cookie.isascii():
            return None
        nonce, separator, mac = cookie.partition(SEPARATOR)
        if not separator or not nonce or not hmac.compare_digest(mac, self._mac(nonce)):
            return None
        return nonce

    def _mac(self, nonce: str) -> str:
        return _encode(hmac.digest(self._key, nonce.encode("ascii"), "sha256"))


def _encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _record(nonce: str) -> str:
    return build_key("identity", "admin_session", hashlib.sha256(nonce.encode("ascii")).hexdigest())
