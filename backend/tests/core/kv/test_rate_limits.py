"""The GCRA limiter in Valkey: bursts, waiting, refill, separate subjects, fail open."""

import asyncio
import time
import uuid
from datetime import timedelta

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from prometheus_client import CollectorRegistry
from redis.asyncio import Redis

from shosai.core.kv.connection import connect_redis
from shosai.core.kv.metrics import KeyValueMetrics
from shosai.core.kv.rate_limits import RateLimit, RateLimiter, subject_key
from tests.core.kv.outages import closed_port, redis_url, silent_server

HOUR = timedelta(hours=1)
VALKEY_PROPERTY = settings(
    max_examples=25,
    deadline=None,
    # Фикстура valkey очищает базу слота один раз после теста; каждый пример берёт
    # свой субъект, поэтому примеры не мешают друг другу.
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)


def as_text(value: bytes | str) -> str:
    """A key as text; the client returns bytes, its annotations promise either."""
    return value.decode() if isinstance(value, bytes) else value


def build_limiter(client: Redis) -> tuple[RateLimiter, CollectorRegistry]:
    registry = CollectorRegistry()
    return RateLimiter(client, KeyValueMetrics(registry)), registry


def decisions(registry: CollectorRegistry, limit: str, decision: str) -> float:
    labels = {"limit": limit, "decision": decision}
    return registry.get_sample_value("shosai_rate_limit_decisions_total", labels) or 0.0


@VALKEY_PROPERTY
@given(burst=st.integers(1, 12), extra=st.integers(1, 5))
async def test_a_burst_passes_then_the_subject_waits(valkey: Redis, burst: int, extra: int) -> None:
    limiter, _ = build_limiter(valkey)
    limit = RateLimit("probe", rate=1, period=HOUR, burst=burst)
    subject = uuid.uuid4().hex

    results = [await limiter.check(limit, subject) for _ in range(burst + extra)]

    allowed, refused = results[:burst], results[burst:]
    assert [result.allowed for result in allowed] == [True] * burst
    assert [result.remaining for result in allowed] == list(range(burst - 1, -1, -1))
    assert all(result.retry_after == timedelta(0) for result in allowed)
    assert not any(result.allowed for result in refused)
    assert all(timedelta(0) < result.retry_after <= HOUR for result in refused)


@VALKEY_PROPERTY
@given(rate=st.integers(1, 1000), burst=st.integers(1, 50), taken=st.integers(1, 50))
async def test_the_state_lives_only_until_the_allowance_refills(
    valkey: Redis, rate: int, burst: int, taken: int
) -> None:
    limiter, _ = build_limiter(valkey)
    limit = RateLimit("probe", rate=rate, period=HOUR, burst=burst)
    subject = uuid.uuid4().hex

    for _ in range(taken):
        await limiter.check(limit, subject)

    refill = limit.interval * min(taken, burst)
    ttl_ms = await valkey.pttl(subject_key(limit, subject))
    assert 0 < ttl_ms <= refill / timedelta(milliseconds=1) + 1


async def test_subjects_do_not_share_an_allowance(valkey: Redis) -> None:
    limiter, _ = build_limiter(valkey)
    limit = RateLimit("sign_in", rate=5, period=timedelta(minutes=1), burst=1)

    first = await limiter.check(limit, "198.51.100.7")
    other = await limiter.check(limit, "203.0.113.9")
    again = await limiter.check(limit, "198.51.100.7")

    assert (first.allowed, other.allowed, again.allowed) == (True, True, False)


async def test_one_interval_later_one_more_request_passes(valkey: Redis) -> None:
    limiter, _ = build_limiter(valkey)
    limit = RateLimit("probe", rate=20, period=timedelta(seconds=1), burst=1)

    assert (await limiter.check(limit, "s")).allowed
    refused = await limiter.check(limit, "s")
    assert not refused.allowed
    assert refused.retry_after <= limit.interval

    await asyncio.sleep(refused.retry_after.total_seconds() + 0.01)
    assert (await limiter.check(limit, "s")).allowed


async def test_no_subject_appears_in_valkey_keys(valkey: Redis) -> None:
    limiter, _ = build_limiter(valkey)
    limit = RateLimit("sign_in", rate=5, period=timedelta(minutes=1), burst=5)

    await limiter.check(limit, "198.51.100.7")

    [key] = [as_text(key) for key in await valkey.keys("shosai:rate:*")]
    assert key.startswith("shosai:rate:sign_in:")
    assert "198.51.100.7" not in key


async def test_decisions_are_counted_per_limit(valkey: Redis) -> None:
    limiter, registry = build_limiter(valkey)
    limit = RateLimit("ai_chat", rate=30, period=timedelta(minutes=1), burst=2)

    for _ in range(3):
        await limiter.check(limit, "user-7")

    assert decisions(registry, "ai_chat", "allowed") == 2
    assert decisions(registry, "ai_chat", "limited") == 1


async def test_a_silent_valkey_lets_requests_through_within_the_deadline() -> None:
    async with silent_server() as port:
        client = connect_redis(redis_url(port), "shosai-tests")
        limiter, registry = build_limiter(client)
        limit = RateLimit("sign_in", rate=5, period=timedelta(minutes=1), burst=5)
        started = time.monotonic()

        decision = await limiter.check(limit, "198.51.100.7")

        assert decision.allowed
        assert time.monotonic() - started < 0.5
        assert decisions(registry, "sign_in", "failed_open") == 1
        await client.aclose()


async def test_a_stopped_valkey_lets_requests_through() -> None:
    client = connect_redis(redis_url(closed_port()), "shosai-tests")
    limiter, registry = build_limiter(client)
    limit = RateLimit("sign_in", rate=5, period=timedelta(minutes=1), burst=5)

    assert (await limiter.check(limit, "198.51.100.7")).allowed
    assert decisions(registry, "sign_in", "failed_open") == 1
    await client.aclose()


@pytest.mark.parametrize(
    ("name", "rate", "period", "burst"),
    [
        ("sign in", 5, timedelta(minutes=1), 5),
        ("user:7", 5, timedelta(minutes=1), 5),
        ("sign_in", 0, timedelta(minutes=1), 5),
        ("sign_in", 5, timedelta(minutes=1), 0),
        ("sign_in", 5, timedelta(0), 5),
        ("sign_in", 2_000_000, timedelta(seconds=1), 5),
    ],
)
def test_a_limit_is_declared_with_sane_values(
    name: str, rate: int, period: timedelta, burst: int
) -> None:
    with pytest.raises(ValueError, match=r"лимит|ключа"):
        RateLimit(name, rate=rate, period=period, burst=burst)
