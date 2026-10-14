"""Billing marks: what each home's hour should hold in `provider_costs` (§16.4, F6 §3.11).

Every call a provider charged for is marked `billed` in the hour of its cost row and the
payer's home — an answer, a paid failure, a minute of a live session, a stream closed
before its usage arrived. A row the writer finds already written under its effect key is
marked `repeated`: the provider charged again, the row exists once (inv-9). So an hour of
a home should hold `billed - repeated` rows, and the reconciliation compares that with the
table. One Valkey hash per home and hour, kept three days.

A mark is best-effort within 50 ms: with Valkey out the call goes on, the miss is counted
and logged once a minute; a missed `billed` can only hide a gap, never invent one.
"""

import asyncio
from collections import Counter as Tally
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final, Literal

from prometheus_client import CollectorRegistry, Counter
from redis.asyncio import Redis

from shosai.core.kernel.homes import Home
from shosai.core.kv.connection import REDIS_FAILURES
from shosai.core.kv.keys import build_key
from shosai.core.observability.outage_log import OutageLog

type BillingField = Literal["billed", "repeated"]

MARK_DEADLINE: Final = timedelta(milliseconds=50)
KEEP_MARKS: Final = timedelta(days=3)
HOUR_FORMAT: Final = "%Y%m%d%H"
# KEYS — хэши часов; ARGV: поле, срок хранения в секундах, затем прибавка к каждому ключу.
MARK_SCRIPT: Final = """
local ttl = tonumber(ARGV[2])
for i, key in ipairs(KEYS) do
  redis.call('HINCRBY', key, ARGV[1], tonumber(ARGV[i + 2]))
  redis.call('EXPIRE', key, ttl)
end
return #KEYS
"""


def hour_of(moment: datetime) -> datetime:
    """The UTC hour a moment falls in."""
    return moment.astimezone(UTC).replace(minute=0, second=0, microsecond=0)


def marks_key(home: Home, hour: datetime) -> str:
    """The hash of a home's hour."""
    return build_key("ai", "billing", home.value, hour_of(hour).strftime(HOUR_FORMAT))


@dataclass(frozen=True, slots=True)
class HourMarks:
    """What a home's hour was marked with."""

    billed: int
    repeated: int

    @property
    def expected_rows(self) -> int:
        """The rows the hour should hold."""
        return self.billed - self.repeated


class BillingMarks:
    """Marks billed and repeated calls per home and hour."""

    def __init__(self, valkey: Redis, registry: CollectorRegistry) -> None:
        self._valkey = valkey
        self._mark = valkey.register_script(MARK_SCRIPT)
        self._missed = Counter(
            "shosai_ai_billing_marks_missed",
            "Пометки оплаченных вызовов, не записанные: Valkey не ответил",
            ("field",),
            registry=registry,
        )
        self._outages = OutageLog("Пометки оплаченных вызовов не записаны: Valkey не ответил")

    async def mark(self, field: BillingField, calls: Iterable[tuple[Home, datetime]]) -> None:
        """Add one to the field of each call's home and hour."""
        tally = Tally((home, hour_of(moment)) for home, moment in calls)
        if not tally:
            return
        try:
            keys = [marks_key(home, hour) for home, hour in tally]
            ttl = int(KEEP_MARKS.total_seconds())
            async with asyncio.timeout(MARK_DEADLINE.total_seconds()):
                await self._mark(keys=keys, args=[field, ttl, *tally.values()])
        except REDIS_FAILURES as failure:
            self._missed.labels(field=field).inc(tally.total())
            self._outages.failed(failure, field=field)

    async def of_hour(self, home: Home, hour: datetime) -> HourMarks:
        """The marks of a home's hour; zero for an hour nothing was marked in."""
        values = await self._valkey.hmget(marks_key(home, hour), ["billed", "repeated"])
        billed, repeated = (int(value or 0) for value in values)
        return HourMarks(billed=billed, repeated=repeated)
