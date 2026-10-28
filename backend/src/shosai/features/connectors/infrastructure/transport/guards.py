"""What keeps provider calls inside the providers' rules, shared by every process (plan §3.6).

- **Cooldown:** a 429 or 503 with `Retry-After` stops that account — or the whole application
  when the provider says so — for every process until the time passes.
- **Breaker per provider:** five 5xx answers or timeouts in 30 seconds stop calls to that
  provider for 20 seconds; one person's 401, 403 or 429 never counts, so a revoked grant
  cannot stop everyone (the draft's breaker counted any exception).
- **Quotas** from the descriptor as GCRA limits (ADR 0011), per application, account or
  connection; **concurrency** per account where the provider bounds it (Outlook: 4).

Valkey that does not answer within 50 ms lets the call through, counted in the outage log:
the provider still answers 429, and a limit is protection, not an invariant.
"""

import asyncio
import hashlib
import secrets
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Final

from redis.asyncio import Redis

from shosai.core.kv.connection import REDIS_FAILURES
from shosai.core.kv.keys import build_key
from shosai.core.kv.rate_limits import RateLimit, RateLimiter
from shosai.core.observability.outage_log import OutageLog
from shosai.features.connectors.contracts.provider import (
    ProviderBusyError,
    ProviderUnavailableError,
)
from shosai.features.connectors.domain.descriptors import LimitSubject, ProviderDescriptor

DEADLINE: Final = 0.05
FAILURES_TO_OPEN: Final = 5
FAILURE_WINDOW_MS: Final = 30_000
OPEN_MS: Final = 20_000
SLOT_STALE_MS: Final = 90_000
SLOT_WAIT: Final = 2.0
SLOT_POLL: Final = 0.05
# KEYS: места аккаунта. ARGV: предел, срок устаревания, метка. Ответ: 1 — место занято.
TAKE_SLOT: Final = """
local t = redis.call('TIME')
local now = tonumber(t[1]) * 1000 + math.floor(tonumber(t[2]) / 1000)
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now - tonumber(ARGV[2]))
if redis.call('ZCARD', KEYS[1]) >= tonumber(ARGV[1]) then return 0 end
redis.call('ZADD', KEYS[1], now, ARGV[3])
redis.call('PEXPIRE', KEYS[1], ARGV[2])
return 1
"""
# KEYS: счётчик сбоев, отметка открытия. ARGV: окно, порог, срок открытия.
FAIL: Final = """
local n = redis.call('INCR', KEYS[1])
if n == 1 then redis.call('PEXPIRE', KEYS[1], ARGV[1]) end
if n >= tonumber(ARGV[2]) then
  redis.call('SET', KEYS[2], '1', 'PX', ARGV[3])
  redis.call('DEL', KEYS[1])
end
return n
"""


def digest(subject: str) -> str:
    """A key part for an account or a connection: no id appears in Valkey's keys."""
    return hashlib.blake2b(subject.encode(), digest_size=16).hexdigest()


class ProviderGuards:
    """Cooldowns, breakers, quotas and concurrency of the providers."""

    def __init__(self, valkey: Redis, limiter: RateLimiter) -> None:
        self._valkey = valkey
        self._limiter = limiter
        self._take = valkey.register_script(TAKE_SLOT)
        self._fail = valkey.register_script(FAIL)
        self._outages = OutageLog("Valkey не ответил защитам вызовов провайдеров")

    async def admit(
        self, descriptor: ProviderDescriptor, subjects: Mapping[LimitSubject, str]
    ) -> None:
        """Refuse a call the provider asked to wait for, a broken provider, a quota spent."""
        provider = descriptor.provider.value
        keys = [build_key("connectors", "breaker", provider, "open")]
        keys += [
            build_key("connectors", "cooldown", provider, digest(value))
            for value in subjects.values()
        ]
        try:
            async with asyncio.timeout(DEADLINE):
                waits = [await self._valkey.pttl(key) for key in keys]
        except REDIS_FAILURES as error:
            self._outages.failed(error, operation="admit", provider=provider)
            waits = []
        if waits and waits[0] > 0:
            raise ProviderUnavailableError
        longest = max((wait for wait in waits[1:] if wait > 0), default=0)
        if longest:
            raise ProviderBusyError(-(-longest // 1000))
        for limit in descriptor.limits:
            subject = subjects.get(limit.subject)
            if subject is None:
                continue
            rate = RateLimit(
                f"conn_{provider}_{limit.name}", limit.requests, limit.period, limit.burst
            )
            decision = await self._limiter.check(rate, subject)
            if not decision.allowed:
                raise ProviderBusyError(max(1, int(decision.retry_after.total_seconds()) + 1))

    async def cool_down(
        self, descriptor: ProviderDescriptor, subject: str, wait: timedelta
    ) -> None:
        """Stop calls of one account (or application) for the time the provider named."""
        key = build_key("connectors", "cooldown", descriptor.provider.value, digest(subject))
        try:
            async with asyncio.timeout(DEADLINE):
                await self._valkey.set(key, "1", px=max(1, int(wait.total_seconds() * 1000)))
        except REDIS_FAILURES as error:
            self._outages.failed(error, operation="cooldown", provider=descriptor.provider.value)

    async def provider_failed(self, descriptor: ProviderDescriptor) -> None:
        """Count a provider-wide failure: a 5xx or a timeout."""
        provider = descriptor.provider.value
        keys = [build_key("connectors", "breaker", provider, name) for name in ("failures", "open")]
        try:
            async with asyncio.timeout(DEADLINE):
                await self._fail(keys=keys, args=[FAILURE_WINDOW_MS, FAILURES_TO_OPEN, OPEN_MS])
        except REDIS_FAILURES as error:
            self._outages.failed(error, operation="breaker", provider=provider)

    @asynccontextmanager
    async def slot(self, descriptor: ProviderDescriptor, account: str) -> AsyncIterator[None]:
        """One of the account's concurrent calls, where the provider bounds them."""
        limit = descriptor.concurrency_per_account
        if limit is None:
            yield
            return
        key = build_key("connectors", "slots", descriptor.provider.value, digest(account))
        member = secrets.token_hex(12)
        taken = await self._wait_slot(key, member, limit)
        try:
            yield
        finally:
            if taken:
                await self._release(key, member)

    async def _wait_slot(self, key: str, member: str, limit: int) -> bool:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + SLOT_WAIT
        while True:
            try:
                async with asyncio.timeout(DEADLINE):
                    if await self._take(keys=[key], args=[limit, SLOT_STALE_MS, member]) == 1:
                        return True
            except REDIS_FAILURES as error:
                self._outages.failed(error, operation="slot")
                return False
            if loop.time() >= deadline:
                raise ProviderBusyError(1)
            await asyncio.sleep(SLOT_POLL)

    async def _release(self, key: str, member: str) -> None:
        try:
            async with asyncio.timeout(DEADLINE):
                await self._valkey.zrem(key, member)
        except REDIS_FAILURES as error:
            self._outages.failed(error, operation="release")
