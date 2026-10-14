"""Spend control: a call reserves its estimate against every ceiling, or none (§3.6).

Before a call is sent, one Lua script checks the kill switch (for an expensive call) and,
for each ceiling the call is under, that what was recorded plus what is reserved plus the
estimate stays within it; then it reserves the estimate everywhere, or nowhere. A
reservation has a lease: one never released — a process that died — frees its amount when
the lease ends. When the cost row is recorded, the counters grow by the actual amount and
the reservation is released, so the estimate is replaced by the actual once (the writer
fills the counters only for a row it inserted).

The call class decides (F6-C4, §13.2): an essential call reserves nothing and is never
refused, only counted; a standard call is refused at a ceiling and goes on, counted, when
Valkey does not answer; an expensive call is refused at a ceiling, while the kill switch is
engaged, and when Valkey does not answer.
"""

import asyncio
import secrets
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Final

import structlog
from prometheus_client import CollectorRegistry
from prometheus_client import Counter as Metric
from redis.asyncio import Redis

from shosai.core.ai.calls import CallClass, CallContext, CallOrigin
from shosai.core.ai.costs.amounts import cost_of
from shosai.core.ai.costs.entries import CostEntry
from shosai.core.ai.errors import AiCallError, AiFailure
from shosai.core.ai.recording import MeteredCall
from shosai.core.ai.results import Usage
from shosai.core.ai.spend.counters import (
    COUNT_SCRIPT,
    RESERVE_SCRIPT,
    SHRINK_SCRIPT,
    Counter,
    Payer,
    counters_of,
    micro_usd,
)
from shosai.core.ai.spend.kill_switch import KILL_SWITCH_KEY, KillSwitch
from shosai.core.kv.connection import REDIS_FAILURES
from shosai.core.observability.outage_log import OutageLog

VALKEY_DEADLINE: Final = 0.05
log = structlog.stdlib.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class Ceilings:
    """The platform's own ceilings in micro-USD: global, and per platform account."""

    global_hour: int
    global_day: int
    platform: Mapping[str, tuple[int, int]]
    lease: timedelta = timedelta(minutes=5)


@dataclass(frozen=True, slots=True)
class Hold:
    """A live reservation: its id and the reservation keys it sits in."""

    reservation: str
    keys: tuple[str, ...]


class SpendMetrics:
    """What spend control decided, by call class and by the ceiling that refused."""

    def __init__(self, registry: CollectorRegistry) -> None:
        self._decisions = Metric(
            "shosai_ai_spend_decisions",
            "Решения контроля расходов: резерв, отказ, пауза, без Valkey",
            ("call_class", "decision"),
            registry=registry,
        )
        self._missed = Metric(
            "shosai_ai_spend_counters_missed",
            "Строки стоимости, не попавшие в счётчики: Valkey не ответил",
            registry=registry,
        )

    def decided(self, call_class: CallClass, decision: str) -> None:
        """One decision about one call."""
        self._decisions.labels(call_class=call_class.value, decision=decision).inc()

    def missed(self) -> None:
        """A recorded row whose amount the counters did not get."""
        self._missed.inc()


class SpendGuard:
    """Reserves, releases and counts the money of model calls."""

    def __init__(
        self, client: Redis, ceilings: Ceilings, kill_switch: KillSwitch, metrics: SpendMetrics
    ) -> None:
        self._reserve = client.register_script(RESERVE_SCRIPT)
        self._shrink = client.register_script(SHRINK_SCRIPT)
        self._count = client.register_script(COUNT_SCRIPT)
        self._ceilings = ceilings
        self._kill_switch = kill_switch
        self._metrics = metrics
        self._outages = OutageLog("Valkey не ответил контролю расходов")

    async def reserve(self, call: MeteredCall, estimate: Usage) -> Hold | None:
        """Reserve the estimate of a call; None when nothing needs to be held."""
        context = call.context
        if context.call_class is CallClass.ESSENTIAL or context.reservation is not None:
            # Встреча деньгами не останавливается; вызов хода Leo списывается с его резерва.
            return None
        amount = micro_usd(cost_of(estimate, call.prices)[0])
        return await self._held(context, amount, secrets.token_hex(12))

    async def release(self, hold: Hold | None) -> None:
        """Drop a reservation; its lease would free it anyway."""
        if hold is not None:
            await self._shrunk(hold, 0)

    async def consume(self, context: CallContext, usage: Usage, call: MeteredCall) -> None:
        """Take a call's actual cost out of the turn reservation it ran under."""
        if context.reservation is None:
            return
        keys = tuple(counter.held for counter, _ in self._limited(context, datetime.now(UTC)))
        amount = micro_usd(cost_of(usage, call.prices)[0])
        await self._shrunk(Hold(context.reservation, keys), max(amount, 1))

    @asynccontextmanager
    async def turn(self, context: CallContext, estimate: Decimal) -> AsyncIterator[CallContext]:
        """A turn's reservation; the context it yields makes the turn's calls draw on it."""
        reservation = f"turn-{secrets.token_hex(12)}"
        hold = await self._held(context, micro_usd(estimate), reservation)
        try:
            yield replace(context, reservation=reservation)
        finally:
            await self.release(hold)

    async def count(self, entries: Sequence[CostEntry]) -> None:
        """Add recorded rows to their counters; a miss is logged and fixed by the rebuild."""
        for entry in entries:
            payer = Payer(
                entry.user_id, entry.platform_account, CallOrigin(entry.origin),
                CallClass(entry.call_class), entry.created_at,
            )  # fmt: skip
            found = counters_of(payer)
            args = [micro_usd(entry.cost_usd), *(int(c.ttl.total_seconds() * 1000) for c in found)]
            try:
                async with asyncio.timeout(VALKEY_DEADLINE):
                    await self._count(keys=[c.key for c in found], args=args)
            except REDIS_FAILURES as error:
                self._metrics.missed()
                self._outages.failed(error, operation="count")

    async def _held(self, context: CallContext, amount: int, reservation: str) -> Hold | None:
        expensive = context.call_class is CallClass.EXPENSIVE
        if expensive and self._kill_switch.forced:
            self._metrics.decided(context.call_class, "paused")
            raise AiCallError(AiFailure.EXPENSIVE_PAUSED)
        limited = self._limited(context, datetime.now(UTC))
        keys = [KILL_SWITCH_KEY]
        for counter, _ in limited:
            keys += [counter.key, counter.held]
        lease = int(self._ceilings.lease.total_seconds() * 1000)
        args: list[str | int] = ["1" if expensive else "0", reservation, amount, lease,
                                 *(ceiling for _, ceiling in limited)]  # fmt: skip
        try:
            async with asyncio.timeout(VALKEY_DEADLINE):
                answer = int(await self._reserve(keys=keys, args=args))
        except REDIS_FAILURES as error:
            self._outages.failed(error, operation="reserve")
            if expensive:
                self._metrics.decided(context.call_class, "paused")
                raise AiCallError(AiFailure.EXPENSIVE_PAUSED) from None
            self._metrics.decided(context.call_class, "unguarded")
            return None
        if answer == -1:
            self._metrics.decided(context.call_class, "paused")
            raise AiCallError(AiFailure.EXPENSIVE_PAUSED)
        if answer > 0:
            self._metrics.decided(context.call_class, "refused")
            log.info("Вызов упёрся в потолок расходов", limit=str(limited[answer - 1][0].limit))
            raise AiCallError(AiFailure.SPEND_LIMIT)
        self._metrics.decided(context.call_class, "held")
        return Hold(reservation, tuple(counter.held for counter, _ in limited))

    def _limited(self, context: CallContext, at: datetime) -> list[tuple[Counter, int]]:
        """The counters of the call that have a ceiling, with it."""
        account = context.platform_account.value if context.platform_account else None
        payer = Payer(context.scope.user_id if context.scope else None, account,
                      context.origin, context.call_class, at)  # fmt: skip
        found = []
        for counter in counters_of(payer):
            ceiling = self._ceiling(context, counter)
            if ceiling is not None:
                found.append((counter, ceiling))
        return found

    def _ceiling(self, context: CallContext, counter: Counter) -> int | None:
        limit = counter.limit
        if limit == "global_hour":
            return self._ceilings.global_hour
        if limit == "global_day":
            return self._ceilings.global_day
        if limit in {"platform_hour", "platform_day"}:
            account = context.platform_account.value if context.platform_account else ""
            caps = self._ceilings.platform.get(account)
            return None if caps is None else caps[0 if limit == "platform_hour" else 1]
        own = [s.micro_usd for s in context.spend_limits if s.period == limit]
        return min(own) if own else None

    async def _shrunk(self, hold: Hold, amount: int) -> None:
        if not hold.keys:
            return
        try:
            async with asyncio.timeout(VALKEY_DEADLINE):
                await self._shrink(keys=list(hold.keys), args=[hold.reservation, amount])
        except REDIS_FAILURES as error:
            # Резерв освободится сам по окончании аренды.
            self._outages.failed(error, operation="release")
