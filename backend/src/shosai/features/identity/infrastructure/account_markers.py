"""Account-state markers in Valkey: revocation without a database read per request (ID-D6).

A ban, freeze, deletion request, password change or "sign out everywhere" writes the
account's token version and state here for the life of an access token (30 minutes);
the authenticator reads it after checking the signature, about 1 ms in the EU, where a
read of the Russian home would cost four round trips of 45 ms. If Valkey does not answer
within 20 ms the request passes on its signature alone: a revoked access token then lives
until it expires, while refresh still reads the home (ADR 0045 point 2).
"""

import asyncio
from collections.abc import Sequence
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
REVOKE_FAMILIES: Final = """
for _, key in ipairs(KEYS) do
    redis.call('SET', key, '1', 'EX', ARGV[1])
end
return #KEYS
"""
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

    async def revoke_families(self, family_ids: Sequence[UUID]) -> bool:
        """Mark single sessions ended after their commit, so their access tokens stop too."""
        if not family_ids:
            return True
        seconds = int(ACCESS_TOKEN_LIFETIME.total_seconds())
        try:
            async with asyncio.timeout(WRITE_DEADLINE.total_seconds()):
                await self._valkey.eval(
                    REVOKE_FAMILIES, len(family_ids), *map(_family_key, family_ids), str(seconds)
                )
        except REDIS_FAILURES:
            log.warning("Метки сессий не записаны: отзыв дойдёт с истечением токенов")
            return False
        return True

    async def read(self, user_id: UUID, family_id: UUID | None) -> MarkerReading:
        """The account's marker and whether the session ended; nothing when Valkey is silent."""
        keys = [_key(user_id)] + ([_family_key(family_id)] if family_id else [])
        try:
            async with asyncio.timeout(READ_DEADLINE.total_seconds()):
                values = await self._valkey.mget(keys)
        except REDIS_FAILURES:
            log.warning("Метка аккаунта не прочитана: запрос проходит по подписи")
            return MarkerReading(None, family_revoked=False)
        family_revoked = len(values) > 1 and values[1] is not None
        if values[0] is None:
            return MarkerReading(None, family_revoked=family_revoked)
        raw = values[0]
        text = raw.decode("ascii") if isinstance(raw, bytes) else str(raw)
        version, _, state = text.partition(SEPARATOR)
        marker = AccountMarker(int(version), AccountState(state))
        return MarkerReading(marker, family_revoked=family_revoked)


@dataclass(frozen=True, slots=True)
class MarkerReading:
    """What Valkey says about a token's account and its session."""

    account: AccountMarker | None
    family_revoked: bool


def _key(user_id: UUID) -> str:
    return build_key("identity", "account", user_id.hex)


def _family_key(family_id: UUID) -> str:
    return build_key("identity", "family_revoked", family_id.hex)
