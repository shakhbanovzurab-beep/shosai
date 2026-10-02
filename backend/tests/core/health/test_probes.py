"""Dependency probes: concurrent, bounded in time, `down` only for the declared failures."""

import time
from datetime import timedelta

import pytest
from redis.asyncio import Redis

from tests.core.kv.outages import closed_port, redis_url, silent_server
from tests.core.storage.adapters import slot_storage
from tests.harness.shared_services import SlotBucket
from whisperer.core.health.dependencies import redis_probe, storage_probe
from whisperer.core.health.probes import DependencyProbe, probe_dependencies
from whisperer.core.kv.connection import connect_redis

QUICK = timedelta(milliseconds=200)


async def test_live_services_are_ok(
    valkey_server: Redis, cache_server: Redis, slot_bucket: SlotBucket
) -> None:
    probes = [
        redis_probe("valkey", valkey_server),
        redis_probe("cache", cache_server),
        storage_probe(slot_storage(slot_bucket).objects),
    ]

    assert await probe_dependencies(probes) == {"valkey": "ok", "cache": "ok", "storage": "ok"}


async def test_silent_and_stopped_services_are_down_within_the_bound() -> None:
    stopped = connect_redis(redis_url(closed_port()), "whisperer-tests")
    async with silent_server() as port:
        silent = connect_redis(redis_url(port), "whisperer-tests")
        other_silent = connect_redis(redis_url(port), "whisperer-tests")
        started = time.monotonic()

        statuses = await probe_dependencies(
            [
                redis_probe("valkey", silent),
                redis_probe("cache", stopped),
                redis_probe("other", other_silent),
            ],
            within=QUICK,
        )

        # Пробы идут одновременно: две молчащие зависимости не складывают ожидание.
        assert time.monotonic() - started < 2 * QUICK.total_seconds()
        for client in (silent, other_silent):
            await client.aclose()
    await stopped.aclose()

    assert statuses == {"valkey": "down", "cache": "down", "other": "down"}


async def test_an_undeclared_error_is_a_bug_not_an_outage() -> None:
    async def broken() -> None:
        message = "проба сломана"
        raise RuntimeError(message)

    probe = DependencyProbe(name="broken", check=broken, failures=(ConnectionError,))

    with pytest.raises(RuntimeError, match="проба сломана"):
        await probe_dependencies([probe])


async def answer() -> None:
    """A dependency that always answers."""


async def test_probe_names_are_unique() -> None:
    probe = DependencyProbe(name="valkey", check=answer, failures=())

    with pytest.raises(ValueError, match="повторяются"):
        await probe_dependencies([probe, probe])
