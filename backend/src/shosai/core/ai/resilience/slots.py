"""The provider-wide semaphore: calls and sessions in flight per provider, in Valkey (§3.5).

Each call or session holds a member of its provider's sorted set, scored by its last
heartbeat on Valkey's clock; a heartbeat every 30 seconds keeps a long session's slot, and a
member silent for 120 seconds — a process that died — is dropped by the next taker. The
limits come from settings, below each provider's quota (OpenRouter 292 at the design point).

Over the limit a call waits a little, then is refused with `rate_limited`; a session is
refused at once with `retry_later`. When Valkey does not answer within 50 ms, the call class
decides (§13.2): essential and standard calls go on without a slot and are counted, expensive
ones are refused with `expensive_paused`.
"""

import asyncio
import contextlib
import secrets
import time
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from typing import Final

from redis.asyncio import Redis

from shosai.core.ai.calls import CallClass, Provider
from shosai.core.ai.errors import AiCallError, AiFailure
from shosai.core.ai.resilience.metrics import ResilienceMetrics
from shosai.core.kv.connection import REDIS_FAILURES
from shosai.core.kv.keys import build_key
from shosai.core.observability.outage_log import OutageLog

VALKEY_DEADLINE: Final = 0.05
HEARTBEAT: Final = 30.0
STALE_MS: Final = 120_000
CALL_WAIT: Final = 2.0
POLL: Final = 0.05
# KEYS: слоты провайдера. ARGV: предел, срок устаревания, метка. Ответ: 1 — слот занят.
TAKE_SCRIPT: Final = """
local t = redis.call('TIME')
local now = tonumber(t[1]) * 1000 + math.floor(tonumber(t[2]) / 1000)
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now - tonumber(ARGV[2]))
if redis.call('ZCARD', KEYS[1]) >= tonumber(ARGV[1]) then return 0 end
redis.call('ZADD', KEYS[1], now, ARGV[3])
redis.call('PEXPIRE', KEYS[1], ARGV[2])
return 1
"""
HEARTBEAT_SCRIPT: Final = """
local t = redis.call('TIME')
local now = tonumber(t[1]) * 1000 + math.floor(tonumber(t[2]) / 1000)
redis.call('ZADD', KEYS[1], 'XX', now, ARGV[2])
redis.call('PEXPIRE', KEYS[1], ARGV[1])
return 1
"""


class ProviderSlots:
    """Slots of every provider, shared by the processes of the plane."""

    def __init__(
        self,
        client: Redis,
        limits: Mapping[Provider, int],
        metrics: ResilienceMetrics,
        call_wait: float = CALL_WAIT,
    ) -> None:
        self._client = client
        self._take = client.register_script(TAKE_SCRIPT)
        self._beat = client.register_script(HEARTBEAT_SCRIPT)
        self._limits = limits
        self._metrics = metrics
        self._call_wait = call_wait
        self._outages = OutageLog("Valkey не ответил семафору провайдера")

    @asynccontextmanager
    async def held(
        self, provider: Provider, call_class: CallClass, *, session: bool
    ) -> AsyncIterator[None]:
        """A slot of the provider for the block; refused when none is free in time."""
        key, member = build_key("ai", "slots", provider.value), secrets.token_hex(12)
        try:
            taken = await self._taken(
                provider, key, member, wait=0.0 if session else self._call_wait
            )
        except REDIS_FAILURES as error:
            self._outages.failed(error, operation="take", provider=provider.value)
            if isinstance(error, TimeoutError):
                # Скрипт мог занять слот, а ответ — опоздать: слот без владельца жил бы 120 с.
                await self._release(key, member)
            if call_class is CallClass.EXPENSIVE:
                self._metrics.slot(provider.value, "refused")
                raise AiCallError(AiFailure.EXPENSIVE_PAUSED) from None
            self._metrics.slot(provider.value, "unguarded")
            yield
            return
        if not taken:
            self._metrics.slot(provider.value, "full")
            raise AiCallError(AiFailure.RETRY_LATER if session else AiFailure.RATE_LIMITED)
        beating = asyncio.create_task(self._keep(key, member), name="ai.slot_heartbeat")
        try:
            yield
        finally:
            beating.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await beating
            await self._release(key, member)

    async def _taken(self, provider: Provider, key: str, member: str, *, wait: float) -> bool:
        """Take a slot, polling until `wait` runs out; Valkey failures propagate."""
        ends_at, waited = time.monotonic() + wait, False
        args: list[int | str] = [self._limits[provider], STALE_MS, member]
        while True:
            async with asyncio.timeout(VALKEY_DEADLINE):
                taken = int(await self._take(keys=[key], args=args)) == 1
            if taken:
                self._metrics.slot(provider.value, "waited" if waited else "taken")
                return True
            if time.monotonic() + POLL > ends_at:
                return False
            waited = True
            await asyncio.sleep(POLL)

    async def _keep(self, key: str, member: str) -> None:
        while True:
            await asyncio.sleep(HEARTBEAT)
            try:
                async with asyncio.timeout(VALKEY_DEADLINE):
                    await self._beat(keys=[key], args=[STALE_MS, member])
            except REDIS_FAILURES as error:
                # Пропущенный пульс не прерывает вызов: слот устареет через 120 с сам.
                self._outages.failed(error, operation="heartbeat")

    async def _release(self, key: str, member: str) -> None:
        try:
            async with asyncio.timeout(VALKEY_DEADLINE):
                await self._client.zrem(key, member)
        except REDIS_FAILURES as error:
            self._outages.failed(error, operation="release")
