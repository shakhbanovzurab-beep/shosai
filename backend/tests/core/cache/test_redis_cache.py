"""The cache over Redis: values with a jittered TTL, hits and misses, an outage is a miss."""

import time
from datetime import timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st
from prometheus_client import CollectorRegistry
from redis.asyncio import Redis

from tests.core.kv.outages import closed_port, redis_url, silent_server
from whisperer.core.cache.metrics import CacheMetrics
from whisperer.core.cache.port import Cache, CacheKey
from whisperer.core.cache.redis_cache import RedisCache, jittered_milliseconds
from whisperer.core.kv.connection import connect_redis

MINUTE = timedelta(minutes=1)
PROFILE = CacheKey("profile.v1", "7f3a")
RATES = CacheKey("rates.v2", "usd")


def build_cache(client: Redis) -> tuple[Cache, CollectorRegistry]:
    registry = CollectorRegistry()
    return RedisCache(client, CacheMetrics(registry)), registry


def operations(registry: CollectorRegistry, namespace: str, operation: str, result: str) -> float:
    labels = {"namespace": namespace, "operation": operation, "result": result}
    return registry.get_sample_value("whisperer_cache_operations_total", labels) or 0.0


async def test_a_stored_value_is_read_back_until_deleted(redis_cache: Redis) -> None:
    cache, registry = build_cache(redis_cache)

    assert await cache.get(PROFILE) is None
    await cache.set(PROFILE, b'{"name":"x"}', MINUTE)
    assert await cache.get(PROFILE) == b'{"name":"x"}'
    await cache.delete(PROFILE)
    assert await cache.get(PROFILE) is None

    assert operations(registry, "profile.v1", "get", "hit") == 1
    assert operations(registry, "profile.v1", "get", "miss") == 2
    assert operations(registry, "profile.v1", "set", "ok") == 1
    assert operations(registry, "profile.v1", "delete", "ok") == 1


async def test_many_values_come_in_order_in_one_call(redis_cache: Redis) -> None:
    cache, registry = build_cache(redis_cache)
    await cache.set(RATES, b"", MINUTE)

    values = await cache.get_many([PROFILE, RATES, CacheKey("rates.v2", "eur")])

    assert values == [None, b"", None]
    await cache.delete()
    assert operations(registry, "rates.v2", "get", "hit") == 1
    assert operations(registry, "rates.v2", "get", "miss") == 1
    assert await cache.get_many([]) == []


async def test_every_entry_expires_within_its_ttl(redis_cache: Redis) -> None:
    cache, _ = build_cache(redis_cache)

    await cache.set(PROFILE, b"v", MINUTE)

    ttl = await redis_cache.pttl(PROFILE.render())
    assert 0.9 * 60_000 - 50 <= ttl <= 60_000


@given(st.integers(1, 10**9))
def test_jitter_only_shortens_the_ttl_by_at_most_a_tenth(milliseconds: int) -> None:
    jittered = jittered_milliseconds(timedelta(milliseconds=milliseconds))

    assert milliseconds - milliseconds // 10 <= jittered <= milliseconds


async def test_a_silent_cache_is_a_miss_within_its_deadline() -> None:
    async with silent_server() as port:
        client = connect_redis(redis_url(port), "whisperer-tests")
        cache, registry = build_cache(client)
        started = time.monotonic()

        assert await cache.get(PROFILE) is None
        await cache.set(PROFILE, b"v", MINUTE)
        await cache.delete(PROFILE)

        assert time.monotonic() - started < 0.5
        await client.aclose()

    for operation in ("get", "set", "delete"):
        assert operations(registry, "profile.v1", operation, "error") == 1


async def test_a_stopped_cache_is_a_miss() -> None:
    client = connect_redis(redis_url(closed_port()), "whisperer-tests")
    cache, registry = build_cache(client)

    assert await cache.get_many([PROFILE, RATES]) == [None, None]

    assert operations(registry, "rates.v2", "get", "error") == 1
    await client.aclose()


@pytest.mark.parametrize(("namespace", "name"), [("profile", "a:b"), ("user@x", "1"), ("", "1")])
def test_a_key_is_made_of_codes_and_ids(namespace: str, name: str) -> None:
    with pytest.raises(ValueError, match="часть ключа"):
        CacheKey(namespace, name)


def test_a_ttl_under_one_millisecond_is_refused() -> None:
    with pytest.raises(ValueError, match="не меньше 1 мс"):
        jittered_milliseconds(timedelta(microseconds=500))
