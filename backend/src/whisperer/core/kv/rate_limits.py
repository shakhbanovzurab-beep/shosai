"""Request rate limits: the generic cell rate algorithm in Valkey (ADR 0011).

State is one key per limit and subject holding the theoretical arrival time (TAT) in
microseconds of Valkey's clock, so processes need no synchronised clocks. One Lua script
reads and moves the TAT atomically in one round trip; the key lives only until the bucket
would be full again. A limit is protection, not an invariant: when Valkey does not answer
within 50 ms, the request is let through, counted and logged (fail open).
"""

import asyncio
import hashlib
from dataclasses import dataclass
from datetime import timedelta
from typing import Final

from redis.asyncio import Redis

from whisperer.core.kv.connection import REDIS_FAILURES
from whisperer.core.kv.keys import build_key, check_key_part
from whisperer.core.kv.metrics import KeyValueMetrics
from whisperer.core.observability.outage_log import OutageLog

RATE_LIMIT_DEADLINE: Final = timedelta(milliseconds=50)
MICROSECOND: Final = timedelta(microseconds=1)
SUBJECT_DIGEST_BYTES: Final = 16
# KEYS[1] — TAT в микросекундах; ARGV[1] — интервал между запросами, ARGV[2] — допуск
# всплеска, оба в микросекундах. Ответ: {пропущен 0|1, ждать мкс, осталось запросов}.
# Числа пишутся через string.format: tostring в Lua дал бы 1.7e+15 и потерял точность.
GCRA_SCRIPT: Final = """
local clock = redis.call('TIME')
local now = tonumber(clock[1]) * 1000000 + tonumber(clock[2])
local interval = tonumber(ARGV[1])
local tolerance = tonumber(ARGV[2])
local tat = tonumber(redis.call('GET', KEYS[1]) or now)
if tat < now then
  tat = now
end
local next_tat = tat + interval
local allow_at = next_tat - tolerance
if now < allow_at then
  return {0, allow_at - now, 0}
end
local ttl = math.ceil((next_tat - now) / 1000)
redis.call('SET', KEYS[1], string.format('%.0f', next_tat), 'PX', string.format('%d', ttl))
return {1, 0, math.floor((now - allow_at) / interval)}
"""


@dataclass(frozen=True, slots=True)
class RateLimit:
    """`rate` requests per `period`, at most `burst` of them at once.

    `name` is stable: it is a metric label and a key part, so it never carries an id.
    Sign-in, 5 per minute per address: `RateLimit("sign_in", 5, timedelta(minutes=1), 5)`.
    """

    name: str
    rate: int
    period: timedelta
    burst: int

    def __post_init__(self) -> None:
        check_key_part(self.name)
        if self.rate < 1 or self.burst < 1:
            message = "частота и всплеск лимита — целые не меньше 1"
            raise ValueError(message)
        if self.interval < MICROSECOND:
            message = "интервал между запросами лимита — не меньше микросекунды"
            raise ValueError(message)

    @property
    def interval(self) -> timedelta:
        """Time one request takes to refill: `period / rate`."""
        return self.period / self.rate


@dataclass(frozen=True, slots=True)
class RateDecision:
    """Whether a request may pass, how many more may pass now and when the next one may."""

    allowed: bool
    remaining: int
    retry_after: timedelta


def subject_key(limit: RateLimit, subject: str) -> str:
    """The state key of a subject: a digest, so no address or id appears in Valkey's keys."""
    digest = hashlib.blake2b(subject.encode(), digest_size=SUBJECT_DIGEST_BYTES).hexdigest()
    return build_key("rate", limit.name, digest)


class RateLimiter:
    """Checks requests against limits shared by every process of the plane."""

    def __init__(self, client: Redis, metrics: KeyValueMetrics) -> None:
        self._script = client.register_script(GCRA_SCRIPT)
        self._metrics = metrics
        self._outages = OutageLog("Valkey не ответил лимиту запросов: запрос пропущен")

    async def check(self, limit: RateLimit, subject: str) -> RateDecision:
        """Take one request from the subject's allowance, or say how long to wait."""
        interval = limit.interval // MICROSECOND
        tolerance = interval * limit.burst
        try:
            async with asyncio.timeout(RATE_LIMIT_DEADLINE.total_seconds()):
                reply = await self._script(
                    keys=[subject_key(limit, subject)], args=[interval, tolerance]
                )
        except REDIS_FAILURES as error:
            self._metrics.count_rate_decision(limit.name, "failed_open")
            self._outages.failed(error, limit=limit.name)
            return RateDecision(allowed=True, remaining=0, retry_after=timedelta(0))
        allowed, wait_microseconds, remaining = (int(value) for value in reply)
        decision = RateDecision(
            allowed=allowed == 1,
            remaining=remaining,
            retry_after=wait_microseconds * MICROSECOND,
        )
        self._metrics.count_rate_decision(limit.name, "allowed" if decision.allowed else "limited")
        return decision
