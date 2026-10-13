"""Breakers per (provider, model): a failing model is skipped for a while (F6-C16, §4.2).

Five failures in 30 seconds open a model's breaker for 20 seconds; then one call is let
through as a probe: its success closes the breaker, its failure opens it again. Failures
are those of the provider — a transport error, 429, 5xx, a stall — never a refusal of the
caller's input or the caller's own deadline. The state lives in Valkey, shared by every
process, on Valkey's clock; when Valkey does not answer within 50 ms, each process keeps its
own breaker with the same rules until Valkey is back.
"""

import asyncio
import hashlib
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Final

from redis.asyncio import Redis

from shosai.core.ai.calls import ModelRef
from shosai.core.ai.resilience.metrics import ResilienceMetrics
from shosai.core.kv.connection import REDIS_FAILURES
from shosai.core.kv.keys import build_key
from shosai.core.observability.outage_log import OutageLog

FAILURES_TO_OPEN: Final = 5
WINDOW_MS: Final = 30_000
OPEN_MS: Final = 20_000
# Проба, не вернувшая ответа за минуту, уступает место следующей.
PROBE_MS: Final = 60_000
VALKEY_DEADLINE: Final = 0.05
# KEYS: состояние, проба. Ответ: 1 — закрыт, 2 — пропущена проба, 0 — открыт.
ALLOW_SCRIPT: Final = """
local t = redis.call('TIME')
local now = tonumber(t[1]) * 1000 + math.floor(tonumber(t[2]) / 1000)
local open_until = tonumber(redis.call('HGET', KEYS[1], 'open_until') or '0')
if open_until == 0 then return 1 end
if now < open_until then return 0 end
if redis.call('SET', KEYS[2], '1', 'NX', 'PX', ARGV[1]) then return 2 end
return 0
"""
# KEYS: состояние, проба, сбои. ARGV: сбоев до открытия, окно, срок открытия, проба, метка.
# Ответ: 1 — выключатель открылся этим сбоем, 0 — нет.
FAILURE_SCRIPT: Final = """
local t = redis.call('TIME')
local now = tonumber(t[1]) * 1000 + math.floor(tonumber(t[2]) / 1000)
local open_until = tonumber(redis.call('HGET', KEYS[1], 'open_until') or '0')
local probing = open_until > 0 and now >= open_until
if not probing then
  redis.call('ZADD', KEYS[3], now, ARGV[5])
  redis.call('ZREMRANGEBYSCORE', KEYS[3], '-inf', now - tonumber(ARGV[2]))
  redis.call('PEXPIRE', KEYS[3], ARGV[2])
  if redis.call('ZCARD', KEYS[3]) < tonumber(ARGV[1]) then return 0 end
end
redis.call('HSET', KEYS[1], 'open_until', now + tonumber(ARGV[3]))
redis.call('PEXPIRE', KEYS[1], tonumber(ARGV[3]) + tonumber(ARGV[4]))
redis.call('DEL', KEYS[2], KEYS[3])
return 1
"""


class Gate(IntEnum):
    """What a breaker lets through: nothing, every call, or one probe."""

    OPEN = 0
    CLOSED = 1
    PROBE = 2


def model_part(model: ModelRef) -> str:
    """The model in a key: its name has `/` and `:`, so it is digested."""
    return hashlib.sha256(model.model.encode()).hexdigest()[:16]


@dataclass(slots=True)
class LocalBreaker:
    """One model's breaker in this process, used while Valkey is out."""

    failures: list[float] = field(default_factory=list)
    open_until: float = 0.0
    probing: bool = False

    def allow(self, now: float) -> Gate:
        """Closed, or open long enough for one probe."""
        if not self.open_until:
            return Gate.CLOSED
        if now < self.open_until or self.probing:
            return Gate.OPEN
        self.probing = True
        return Gate.PROBE

    def failed(self, now: float) -> bool:
        """Count a failure; True when it opens the breaker."""
        if not (self.open_until and now >= self.open_until):
            self.failures = [moment for moment in self.failures if moment > now - WINDOW_MS / 1000]
            self.failures.append(now)
            if len(self.failures) < FAILURES_TO_OPEN:
                return False
        self.open_until, self.probing, self.failures = now + OPEN_MS / 1000, False, []
        return True


class Breakers:
    """Breakers of every model, shared by the processes through Valkey."""

    def __init__(
        self,
        client: Redis,
        metrics: ResilienceMetrics,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._allow = client.register_script(ALLOW_SCRIPT)
        self._failure = client.register_script(FAILURE_SCRIPT)
        self._client = client
        self._metrics = metrics
        self._clock = clock
        self._local: dict[ModelRef, LocalBreaker] = {}
        self._outages = OutageLog("Valkey не ответил выключателю: действует выключатель процесса")

    async def allow(self, model: ModelRef) -> Gate:
        """Whether a call may go to the model now, and whether it is the probe."""
        state, probe, _ = self._keys(model)
        try:
            async with asyncio.timeout(VALKEY_DEADLINE):
                gate = Gate(int(await self._allow(keys=[state, probe], args=[PROBE_MS])))
        except REDIS_FAILURES as error:
            self._outages.failed(error, operation="allow")
            gate = self._local.setdefault(model, LocalBreaker()).allow(self._clock())
        if gate is Gate.OPEN:
            self._metrics.rejected(model.provider.value, model.model)
        return gate

    async def failed(self, model: ModelRef) -> None:
        """Count a provider failure of the model."""
        state, probe, failures = self._keys(model)
        args: list[int | str] = [
            FAILURES_TO_OPEN,
            WINDOW_MS,
            OPEN_MS,
            PROBE_MS,
            secrets.token_hex(8),
        ]
        try:
            async with asyncio.timeout(VALKEY_DEADLINE):
                opened = int(await self._failure(keys=[state, probe, failures], args=args)) == 1
        except REDIS_FAILURES as error:
            self._outages.failed(error, operation="failure")
            opened = self._local.setdefault(model, LocalBreaker()).failed(self._clock())
        if opened:
            self._metrics.breaker(model.provider.value, model.model, "opened")

    async def succeeded(self, model: ModelRef, gate: Gate) -> None:
        """A call was answered; a probe's answer closes the breaker, others change nothing.

        Ordinary answers leave the failures counted: five in 30 seconds open the breaker
        even between answers, as F6-C16 states.
        """
        if gate is not Gate.PROBE:
            return
        self._local.pop(model, None)
        try:
            async with asyncio.timeout(VALKEY_DEADLINE):
                closed = int(await self._client.delete(*self._keys(model)))
        except REDIS_FAILURES as error:
            self._outages.failed(error, operation="success")
            return
        if closed:
            self._metrics.breaker(model.provider.value, model.model, "closed")

    @staticmethod
    def _keys(model: ModelRef) -> tuple[str, str, str]:
        part = (model.provider.value, model_part(model))
        return (
            build_key("ai", "breaker", *part),
            build_key("ai", "breaker", *part, "probe"),
            build_key("ai", "breaker", *part, "failures"),
        )
