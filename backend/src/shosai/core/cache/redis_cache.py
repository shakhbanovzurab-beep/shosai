"""The cache port over the Redis cache container of the plane (`allkeys-lru`, §4.2).

Cache-aside: a slice reads the cache, on a miss reads PostgreSQL and stores the value.
The container sits next to the processes, so a call waits at most 20 ms: past that the
database read is the faster path, and a slow cache must not slow the request. A failure
is a miss — counted, logged at most once per interval — and never an error for the caller.
TTLs are shortened by a random part of up to 10%, so entries written together do not
expire together and send their misses to the database at the same moment.
"""

import asyncio
import secrets
from collections import Counter
from collections.abc import Sequence
from datetime import timedelta
from typing import Final

from redis.asyncio import Redis

from shosai.core.cache.metrics import CacheMetrics, CacheOperation, CacheResult
from shosai.core.cache.port import CacheKey
from shosai.core.kv.connection import REDIS_FAILURES
from shosai.core.observability.outage_log import OutageLog

CACHE_DEADLINE: Final = timedelta(milliseconds=20)
TTL_JITTER_SHARE: Final = 0.1


def jittered_milliseconds(ttl: timedelta) -> int:
    """The TTL in milliseconds, shortened by a random part of up to `TTL_JITTER_SHARE`."""
    milliseconds = int(ttl / timedelta(milliseconds=1))
    if milliseconds < 1:
        message = "время жизни записи кэша — не меньше 1 мс"
        raise ValueError(message)
    spread = int(milliseconds * TTL_JITTER_SHARE)
    return milliseconds - secrets.randbelow(spread + 1)


def lookup_result(value: bytes | None) -> CacheResult:
    """A hit for any stored value, the empty one included."""
    return "miss" if value is None else "hit"


class RedisCache:
    """`Cache` over one Redis client; slices receive it by injection as the port."""

    def __init__(self, client: Redis, metrics: CacheMetrics) -> None:
        self._client = client
        self._metrics = metrics
        self._outages = OutageLog("Кэш не ответил: запрос идёт в источник")

    async def get(self, key: CacheKey) -> bytes | None:
        """The cached value, or None on a miss or when the cache does not answer."""
        (value,) = await self.get_many([key])
        return value

    async def get_many(self, keys: Sequence[CacheKey]) -> list[bytes | None]:
        """The values in the order of `keys`, None for each miss; one round trip."""
        if not keys:
            return []
        try:
            async with asyncio.timeout(CACHE_DEADLINE.total_seconds()):
                replies = await self._client.mget([key.render() for key in keys])
        except REDIS_FAILURES as error:
            self._failed("get", keys, error)
            return [None] * len(keys)
        values = [reply if isinstance(reply, bytes) else None for reply in replies]
        results = Counter(
            (key.namespace, lookup_result(value)) for key, value in zip(keys, values, strict=True)
        )
        for (namespace, result), amount in results.items():
            self._metrics.count(namespace, "get", result, amount)
        return values

    async def set(self, key: CacheKey, value: bytes, ttl: timedelta) -> None:
        """Store a value for at most `ttl`; a failure is logged and counted, never raised."""
        milliseconds = jittered_milliseconds(ttl)
        try:
            async with asyncio.timeout(CACHE_DEADLINE.total_seconds()):
                await self._client.set(key.render(), value, px=milliseconds)
        except REDIS_FAILURES as error:
            self._failed("set", [key], error)
            return
        self._metrics.count(key.namespace, "set", "ok")

    async def delete(self, *keys: CacheKey) -> None:
        """Forget entries; when the cache does not answer, their TTL bounds the staleness."""
        if not keys:
            return
        try:
            async with asyncio.timeout(CACHE_DEADLINE.total_seconds()):
                await self._client.delete(*(key.render() for key in keys))
        except REDIS_FAILURES as error:
            self._failed("delete", keys, error)
            return
        for namespace, amount in Counter(key.namespace for key in keys).items():
            self._metrics.count(namespace, "delete", "ok", amount)

    def _failed(
        self, operation: CacheOperation, keys: Sequence[CacheKey], error: BaseException
    ) -> None:
        for namespace, amount in Counter(key.namespace for key in keys).items():
            self._metrics.count(namespace, operation, "error", amount)
        self._outages.failed(error, operation=operation)
