"""Account-state markers in Valkey: revocation without a database read per request (ID-D6).

A ban, freeze, deletion request, password change or "sign out everywhere" writes the
account's token version and state here for the life of an access token (30 minutes);
the authenticator reads it after checking the signature, about 1 ms in the EU, where a
read of the Russian home would cost four round trips of 45 ms. If Valkey does not answer
within 20 ms the request passes on its signature alone: a revoked access token then lives
until it expires, while refresh still reads the home (ADR 0045 point 2).
"""

import asyncio
from dataclasses import dataclass
from datetime import timedelta
from typing import Final
from uuid import UUID

import structlog
from redis.asyncio import Redis

from shosai.core.kv.connection import REDIS_FAILURES
from shosai.core.kv.keys import build_key
from shosai.features.identity.domain.accounts import AccountState
from shosai.features.identity.domain.tokens import ACCESS_TOKEN_LIFETIME

READ_DEADLINE: Final = timedelta(milliseconds=20)
WRITE_DEADLINE: Final = timedelta(milliseconds=200)
SEPARATOR: Final = ":"
log = structlog.stdlib.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class AccountMarker:
    """The token version and state an account had when it last changed."""

    token_version: int
    state: AccountState


class AccountMarkers:
    """Markers by account id, kept as long as an access token lives."""

    def __init__(self, valkey: Redis) -> None:
        self._valkey = valkey

    async def write(self, user_id: UUID, marker: AccountMarker) -> bool:
        """Record a change after its commit; False (logged) when Valkey did not take it."""
        value = f"{marker.token_version}{SEPARATOR}{marker.state.value}"
        seconds = int(ACCESS_TOKEN_LIFETIME.total_seconds())
        try:
            async with asyncio.timeout(WRITE_DEADLINE.total_seconds()):
                await self._valkey.set(_key(user_id), value, ex=seconds)
        except REDIS_FAILURES:
            log.warning("Метка аккаунта не записана: отзыв дойдёт с истечением токена")
            return False
        return True

    async def read(self, user_id: UUID) -> AccountMarker | None:
        """The account's marker, or None when there is none or Valkey is silent."""
        try:
            async with asyncio.timeout(READ_DEADLINE.total_seconds()):
                value = await self._valkey.get(_key(user_id))
        except REDIS_FAILURES:
            log.warning("Метка аккаунта не прочитана: запрос проходит по подписи")
            return None
        if value is None:
            return None
        text = value.decode("ascii") if isinstance(value, bytes) else str(value)
        version, _, state = text.partition(SEPARATOR)
        return AccountMarker(int(version), AccountState(state))


def _key(user_id: UUID) -> str:
    return build_key("identity", "account", user_id.hex)
