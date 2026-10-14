"""At most two interactive streams or sessions of one user in flight (F6-C20, F6-D6).

A user's open `stream_chat` calls and live sessions started by the person (`interactive`)
are members of the user's sorted set in Valkey, scored by their last heartbeat; a member
silent for 120 seconds — a process that died — is dropped by the next arrival. A standard or
expensive stream over the cap is refused with `rate_limited` and a `Retry-After`; an
essential one — a meeting, standard transcription — joins the set and counts, but is
admitted whatever the count (inv-13). Background and system calls are not counted. When
Valkey does not answer within 50 ms the cap is not enforced; spend control still decides
what an outage refuses (§3.6).
"""

import asyncio
import contextlib
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Final

from redis.asyncio import Redis

from shosai.core.ai.calls import CallClass, CallContext, CallOrigin
from shosai.core.ai.errors import AiCallError, AiFailure
from shosai.core.kv.connection import REDIS_FAILURES
from shosai.core.kv.keys import build_key
from shosai.core.observability.outage_log import OutageLog

VALKEY_DEADLINE: Final = 0.05
HEARTBEAT: Final = 30.0
STALE_MS: Final = 120_000
RETRY_AFTER_SECONDS: Final = 5
# KEYS: потоки пользователя. ARGV: предел, срок устаревания, метка, пускать ли сверх предела.
# Ответ: 1 — поток учтён, 0 — предел достигнут.
JOIN_SCRIPT: Final = """
local t = redis.call('TIME')
local now = tonumber(t[1]) * 1000 + math.floor(tonumber(t[2]) / 1000)
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now - tonumber(ARGV[2]))
if ARGV[4] ~= '1' and redis.call('ZCARD', KEYS[1]) >= tonumber(ARGV[1]) then return 0 end
redis.call('ZADD', KEYS[1], now, ARGV[3])
redis.call('PEXPIRE', KEYS[1], ARGV[2])
return 1
"""
BEAT_SCRIPT: Final = """
local t = redis.call('TIME')
local now = tonumber(t[1]) * 1000 + math.floor(tonumber(t[2]) / 1000)
redis.call('ZADD', KEYS[1], 'XX', now, ARGV[2])
redis.call('PEXPIRE', KEYS[1], ARGV[1])
return 1
"""


class StreamCap:
    """Counts each user's interactive streams and refuses the one over the cap."""

    def __init__(self, client: Redis, cap: int) -> None:
        self._client = client
        self._join = client.register_script(JOIN_SCRIPT)
        self._beat = client.register_script(BEAT_SCRIPT)
        self._cap = cap
        self._outages = OutageLog("Valkey не ответил лимиту потоков: лимит не действует")

    @asynccontextmanager
    async def held(self, context: CallContext) -> AsyncIterator[None]:
        """A place among the user's streams for the block; refused over the cap."""
        user = context.scope.user_id if context.scope else None
        if context.origin is not CallOrigin.INTERACTIVE or user is None:
            yield
            return
        key, member = build_key("ai", "streams", user.hex), secrets.token_hex(12)
        essential = "1" if context.call_class is CallClass.ESSENTIAL else "0"
        args: list[str | int] = [self._cap, STALE_MS, member, essential]
        try:
            async with asyncio.timeout(VALKEY_DEADLINE):
                joined = int(await self._join(keys=[key], args=args)) == 1
        except REDIS_FAILURES as error:
            self._outages.failed(error, operation="join")
            yield
            return
        if not joined:
            raise AiCallError(AiFailure.RATE_LIMITED, retry_after=RETRY_AFTER_SECONDS)
        beating = asyncio.create_task(self._keep(key, member), name="ai.stream_heartbeat")
        try:
            yield
        finally:
            beating.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await beating
            try:
                async with asyncio.timeout(VALKEY_DEADLINE):
                    await self._client.zrem(key, member)
            except REDIS_FAILURES as error:
                # Не ушёл — уйдёт сам через 120 с без пульса.
                self._outages.failed(error, operation="leave")

    async def _keep(self, key: str, member: str) -> None:
        while True:
            await asyncio.sleep(HEARTBEAT)
            try:
                async with asyncio.timeout(VALKEY_DEADLINE):
                    await self._beat(keys=[key], args=[STALE_MS, member])
            except REDIS_FAILURES as error:
                self._outages.failed(error, operation="heartbeat")
