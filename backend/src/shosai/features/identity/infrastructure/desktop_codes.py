"""One-time desktop sign-in codes in Valkey: 120 seconds, taken by GETDEL (ADR 0045 point 9).

A signed-in browser asks for a code and hands it to the desktop app through `shosai://auth`;
the app exchanges it for its own tokens. The code is stored only as its SHA-256 with the
account id, its home and the app's PKCE challenge, and GETDEL takes it atomically, so of
twenty simultaneous exchanges exactly one succeeds (the draft read and then marked used).
No personal data: ids, the home and a hash. No `desktop_auth_codes` table exists.
"""

import asyncio
import hashlib
import secrets
from dataclasses import dataclass
from datetime import timedelta
from typing import Final
from uuid import UUID

from redis.asyncio import Redis

from shosai.core.kernel.homes import Home
from shosai.core.kv.connection import REDIS_FAILURES
from shosai.core.kv.keys import build_key

CODE_LIFETIME: Final = timedelta(seconds=120)
CODE_BYTES: Final = 32
DEADLINE: Final = timedelta(milliseconds=200)
SEPARATOR: Final = "|"


class DesktopCodesUnavailableError(Exception):
    """Valkey did not answer: no code can be issued or taken now."""


@dataclass(frozen=True, slots=True)
class DesktopGrant:
    """What a code stands for: the account, its home and the app's challenge if any."""

    user_id: UUID
    home: Home
    challenge: str | None


class DesktopCodes:
    """Issue and take desktop codes."""

    def __init__(self, valkey: Redis) -> None:
        self._valkey = valkey

    async def issue(self, grant: DesktopGrant) -> str:
        """A new code for the grant, valid 120 seconds."""
        code = secrets.token_urlsafe(CODE_BYTES)
        value = SEPARATOR.join((str(grant.user_id), grant.home.value, grant.challenge or ""))
        try:
            async with asyncio.timeout(DEADLINE.total_seconds()):
                await self._valkey.set(_key(code), value, ex=int(CODE_LIFETIME.total_seconds()))
        except REDIS_FAILURES as error:
            raise DesktopCodesUnavailableError from error
        return code

    async def take(self, code: str) -> DesktopGrant | None:
        """The grant of a live code, which is gone after this call; None otherwise."""
        try:
            async with asyncio.timeout(DEADLINE.total_seconds()):
                value = await self._valkey.getdel(_key(code))
        except REDIS_FAILURES as error:
            raise DesktopCodesUnavailableError from error
        if value is None:
            return None
        text = value.decode("ascii") if isinstance(value, bytes) else str(value)
        user_id, home, challenge = text.split(SEPARATOR)
        return DesktopGrant(UUID(user_id), Home(home), challenge or None)


def _key(code: str) -> str:
    digest = hashlib.sha256(code.encode("utf-8")).hexdigest()
    return build_key("identity", "desktop_code", digest)
