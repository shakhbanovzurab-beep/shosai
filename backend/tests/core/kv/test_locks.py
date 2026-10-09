"""Distributed locks: one holder, safe release and extension, a stated outage policy."""

import asyncio
import time
from contextlib import AsyncExitStack
from datetime import timedelta

import pytest
from prometheus_client import CollectorRegistry
from redis.asyncio import Redis

from shosai.core.kv.connection import connect_redis
from shosai.core.kv.locks import (
    DistributedLocks,
    LockOutagePolicy,
    LockUnavailableError,
    lock_milliseconds,
)
from shosai.core.kv.metrics import KeyValueMetrics
from tests.core.db.tcp_proxy import CountingProxy
from tests.core.kv.outages import closed_port, redis_url, silent_server, through, upstream_of

CLOSED = LockOutagePolicy.FAIL_CLOSED
OPEN = LockOutagePolicy.FAIL_OPEN
LONG = timedelta(seconds=30)
LOCK_KEY = "shosai:lock:relay.ru"


def build_locks(client: Redis) -> tuple[DistributedLocks, CollectorRegistry]:
    registry = CollectorRegistry()
    return DistributedLocks(client, KeyValueMetrics(registry)), registry


def outages(registry: CollectorRegistry, policy: LockOutagePolicy) -> float:
    value = registry.get_sample_value("shosai_lock_outages_total", {"policy": policy.value})
    return value or 0.0


async def test_a_lock_has_one_holder_at_a_time(valkey: Redis) -> None:
    locks, _ = build_locks(valkey)

    async with locks.hold("relay.ru", ttl=LONG, outage=CLOSED) as first:
        async with locks.hold("relay.ru", ttl=LONG, outage=CLOSED) as second:
            assert second is None
        assert first is not None
        assert first.guarded
        assert 29_000 < await valkey.pttl(LOCK_KEY) <= 30_000

    assert await valkey.exists(LOCK_KEY) == 0
    async with locks.hold("relay.ru", ttl=LONG, outage=CLOSED) as third:
        assert third is not None


async def fail_under_the_lock(locks: DistributedLocks) -> None:
    async with locks.hold("relay.ru", ttl=LONG, outage=CLOSED):
        message = "работа упала"
        raise RuntimeError(message)


async def test_the_lock_is_released_when_the_guarded_work_fails(valkey: Redis) -> None:
    locks, _ = build_locks(valkey)

    with pytest.raises(RuntimeError, match="работа упала"):
        await fail_under_the_lock(locks)

    assert await valkey.exists(LOCK_KEY) == 0


async def test_an_expired_holder_touches_nothing_of_the_next_holder(valkey: Redis) -> None:
    locks, _ = build_locks(valkey)

    async with AsyncExitStack() as stale_scope:
        stale = await stale_scope.enter_async_context(
            locks.hold("relay.ru", ttl=timedelta(milliseconds=50), outage=CLOSED)
        )
        assert stale is not None
        await asyncio.sleep(0.12)
        async with locks.hold("relay.ru", ttl=LONG, outage=CLOSED) as fresh:
            assert fresh is not None
            assert await stale.extend(LONG) is False
            # Устаревший держатель выходит из блока, пока свежий ещё держит блокировку.
            await stale_scope.aclose()
            assert await valkey.pttl(LOCK_KEY) > 29_000


async def test_extension_prolongs_the_lock(valkey: Redis) -> None:
    locks, _ = build_locks(valkey)

    async with locks.hold("relay.ru", ttl=timedelta(seconds=1), outage=CLOSED) as lease:
        assert lease is not None
        assert await lease.extend(LONG) is True
        assert await valkey.pttl(LOCK_KEY) > 29_000


async def test_fail_closed_stops_the_work_within_the_deadline() -> None:
    async with silent_server() as port:
        client = connect_redis(redis_url(port), "shosai-tests")
        locks, registry = build_locks(client)
        started = time.monotonic()

        with pytest.raises(LockUnavailableError):
            async with locks.hold("relay.ru", ttl=LONG, outage=CLOSED):
                pytest.fail("работа под блокировкой не должна начаться")

        assert time.monotonic() - started < 0.5
        assert outages(registry, CLOSED) == 1
        await client.aclose()


async def test_fail_open_runs_the_work_unguarded() -> None:
    client = connect_redis(redis_url(closed_port()), "shosai-tests")
    locks, registry = build_locks(client)

    async with locks.hold("relay.ru", ttl=LONG, outage=OPEN) as lease:
        assert lease is not None
        assert not lease.guarded
        assert await lease.extend(LONG) is True

    assert outages(registry, OPEN) == 1
    await client.aclose()


async def test_a_lost_valkey_keeps_fail_open_work_going(valkey: Redis) -> None:
    proxy = CountingProxy(upstream_of(valkey))
    client = connect_redis(through(valkey, await proxy.start()), "shosai-tests")
    locks, registry = build_locks(client)

    async with locks.hold("relay.ru", ttl=LONG, outage=OPEN) as lease:
        assert lease is not None
        assert lease.guarded
        await proxy.stop()
        assert await lease.extend(LONG) is True

    assert outages(registry, OPEN) == 2
    await client.aclose()


async def test_a_lost_valkey_ends_an_extension_under_fail_closed(valkey: Redis) -> None:
    proxy = CountingProxy(upstream_of(valkey))
    client = connect_redis(through(valkey, await proxy.start()), "shosai-tests")
    locks, registry = build_locks(client)

    async with locks.hold("relay.ru", ttl=LONG, outage=CLOSED) as lease:
        assert lease is not None
        await proxy.stop()
        with pytest.raises(LockUnavailableError):
            await lease.extend(LONG)

    # Освобождение тоже не дошло: блокировку снимет TTL, а работа не стала неудачной.
    assert outages(registry, CLOSED) == 2
    assert await valkey.exists(LOCK_KEY) == 1
    await client.aclose()


@pytest.mark.parametrize("ttl", [timedelta(0), timedelta(microseconds=999), timedelta(seconds=-1)])
def test_a_ttl_under_one_millisecond_is_refused(ttl: timedelta) -> None:
    with pytest.raises(ValueError, match="не меньше 1 мс"):
        lock_milliseconds(ttl)


async def test_a_lock_name_is_a_code_not_free_text() -> None:
    client = connect_redis(redis_url(closed_port()), "shosai-tests")
    locks, _ = build_locks(client)

    with pytest.raises(ValueError, match="часть ключа"):
        async with locks.hold("user anna@example.com", ttl=LONG, outage=CLOSED):
            pytest.fail("блокировка с таким именем не берётся")
    await client.aclose()
