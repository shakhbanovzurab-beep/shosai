"""The debug switches in Valkey and their follower in every process (§16.7, F5 plan §3.13).

One sorted set holds every switch, its score the switch's end: a switch ends by itself,
and a process reads all of them in one round trip. An operator turns one on for up to an
hour with `shosai observability debug`. Every process reads the set every 15 s and hands
the switches to its log gate; each change is one log line. Valkey out of reach keeps the
switches the process already has: they still end on time, since the gate checks the end.
"""

import asyncio
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Final
from uuid import UUID

import structlog
from redis.asyncio import Redis

from shosai.core.kv.connection import REDIS_FAILURES
from shosai.core.kv.keys import build_key
from shosai.core.observability.debug_logs import DebugLogGate, DebugScope, DebugSwitch

DEBUG_SWITCHES_KEY: Final = build_key("observability", "debug")
LONGEST: Final = timedelta(hours=1)
REFRESH_EVERY: Final = timedelta(seconds=15)
VALKEY_DEADLINE: Final = 1.0
log = structlog.stdlib.get_logger(__name__)


def member(scope: DebugScope, target: UUID) -> str:
    """The set member of a switch: `user:<id>` or `org:<id>`."""
    return f"{scope.value}:{target}"


def parse_member(raw: bytes | str, score: float) -> DebugSwitch:
    """A switch from its member and its score."""
    text = raw.decode() if isinstance(raw, bytes) else raw
    scope, _, target = text.partition(":")
    return DebugSwitch(DebugScope(scope), UUID(target), datetime.fromtimestamp(score, UTC))


class DebugSwitches:
    """The switches of the platform, in one Valkey sorted set."""

    def __init__(self, valkey: Redis) -> None:
        self._valkey = valkey

    async def switch_on(
        self, scope: DebugScope, target: UUID, duration: timedelta, now: datetime
    ) -> DebugSwitch:
        """Open the lines of the account or company for `duration`, at most an hour."""
        if not timedelta(0) < duration <= LONGEST:
            message = f"отладка включается на срок до {int(LONGEST.total_seconds() // 60)} минут"
            raise ValueError(message)
        switch = DebugSwitch(scope, target, now + duration)
        # Две команды разовой команды оператора; процессы только читают множество.
        async with asyncio.timeout(VALKEY_DEADLINE):
            await self._valkey.zremrangebyscore(DEBUG_SWITCHES_KEY, "-inf", now.timestamp())
            await self._valkey.zadd(
                DEBUG_SWITCHES_KEY, {member(scope, target): switch.ends_at.timestamp()}
            )
        return switch

    async def switch_off(self, scope: DebugScope, target: UUID) -> bool:
        """End the switch now; False when it was not on."""
        async with asyncio.timeout(VALKEY_DEADLINE):
            removed = await self._valkey.zrem(DEBUG_SWITCHES_KEY, member(scope, target))
        return bool(removed)

    async def active(self, now: datetime) -> tuple[DebugSwitch, ...]:
        """The switches that have not ended."""
        async with asyncio.timeout(VALKEY_DEADLINE):
            rows = await self._valkey.zrangebyscore(
                DEBUG_SWITCHES_KEY, f"({now.timestamp()}", "+inf", withscores=True
            )
        return tuple(parse_row(row) for row in rows)


def parse_row(row: object) -> DebugSwitch:
    """A switch from one `(member, score)` row of the set."""
    match row:
        case (bytes() | str() as raw, int() | float() as score):
            return parse_member(raw, float(score))
        case _:
            message = "строка множества отладочных переключателей — не пара (член, срок)"
            raise TypeError(message)


def log_changes(before: Sequence[DebugSwitch], after: Sequence[DebugSwitch]) -> None:
    """One line per switch the process starts or stops following."""
    old = {(switch.scope, switch.target) for switch in before}
    new = {(switch.scope, switch.target) for switch in after}
    for switch in after:
        if (switch.scope, switch.target) not in old:
            log.info("Отладочные журналы включены", scope=switch.scope.value,
                     **{switch.scope.log_key: str(switch.target)},
                     ends_at=switch.ends_at.isoformat())  # fmt: skip
    for switch in before:
        if (switch.scope, switch.target) not in new:
            log.info("Отладочные журналы выключены", scope=switch.scope.value,
                     **{switch.scope.log_key: str(switch.target)})  # fmt: skip


async def follow(switches: DebugSwitches, gate: DebugLogGate, every: timedelta) -> None:
    """Read the switches every `every` and hand them to the gate, until cancelled."""
    current: tuple[DebugSwitch, ...] = ()
    reachable = True
    while True:
        try:
            fresh = await switches.active(datetime.now(UTC))
        except REDIS_FAILURES as error:
            if reachable:
                log.warning("Valkey недоступен: отладочные переключатели не обновлены",
                            error_type=type(error).__name__)  # fmt: skip
            reachable = False
        else:
            reachable = True
            log_changes(current, fresh)
            current = fresh
            gate.apply(current)
        await asyncio.sleep(every.total_seconds())


@asynccontextmanager
async def following_debug_switches(
    valkey: Redis, gate: DebugLogGate, every: timedelta = REFRESH_EVERY
) -> AsyncIterator[asyncio.Task[None]]:
    """The follower of the process while the block runs; the gate is closed after it."""
    task = asyncio.create_task(follow(DebugSwitches(valkey), gate, every), name="debug-switches")
    try:
        yield task
    finally:
        task.cancel()
        # Ждать конца, не поднимая его отмену: внешнюю отмену это не глотает.
        await asyncio.wait({task})
        gate.close()
