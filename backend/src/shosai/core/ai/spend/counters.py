"""Spend counters in Valkey: which a call fills and what each is kept for (§3.6).

Money is integer micro-USD. A counter holds what was recorded in its period; a hash beside
it holds the live reservations, `id → amount:expiry` on Valkey's clock. Periods are UTC:
the hour, the day and the month of the call. Whose counters a call fills:

- every call: the global hour and day, whatever its class — the ceilings never stop an
  essential call, but they see it;
- a platform account's call: the account's hour and day (F6-C19);
- a user's interactive call that is not essential: the user's hour, day and month, and the
  expensive month when it is expensive (F6-D6: only interactive calls count toward the
  user's caps, and meetings never fill them, inv-13);
- a user's background call: the user's background day (Leo §5.4).
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import ROUND_CEILING, Decimal
from typing import Final
from uuid import UUID

from shosai.core.ai.calls import CallClass, CallOrigin, SpendPeriod
from shosai.core.kv.keys import build_key

MICRO: Final = Decimal(1_000_000)
TTLS: Final = {
    "hour": timedelta(hours=2),
    "day": timedelta(days=2),
    "month": timedelta(days=35),
}
# KEYS: аварийный выключатель, затем пары (счётчик, резервы). ARGV: проверять ли выключатель,
# id резерва, сумма, аренда в мс, затем потолок каждой пары.
# Ответ: -1 — выключатель включён, 0 — резерв взят, i — превышен потолок пары i.
RESERVE_SCRIPT: Final = """
local t = redis.call('TIME')
local now = tonumber(t[1]) * 1000 + math.floor(tonumber(t[2]) / 1000)
if ARGV[1] == '1' and redis.call('EXISTS', KEYS[1]) == 1 then return -1 end
local amount = tonumber(ARGV[3])
local pairs_count = (#KEYS - 1) / 2
for i = 1, pairs_count do
  local held = KEYS[2 * i + 1]
  local reserved = 0
  local entries = redis.call('HGETALL', held)
  for j = 1, #entries, 2 do
    local value, expires = string.match(entries[j + 1], '^(%d+):(%d+)$')
    if tonumber(expires) <= now then
      redis.call('HDEL', held, entries[j])
    else
      reserved = reserved + tonumber(value)
    end
  end
  local spent = tonumber(redis.call('GET', KEYS[2 * i]) or '0')
  if spent + reserved + amount > tonumber(ARGV[4 + i]) then return i end
end
local entry = string.format('%d:%d', amount, now + tonumber(ARGV[4]))
for i = 1, pairs_count do
  redis.call('HSET', KEYS[2 * i + 1], ARGV[2], entry)
  redis.call('PEXPIRE', KEYS[2 * i + 1], tonumber(ARGV[4]) * 2)
end
return 0
"""
# KEYS: резервы. ARGV: id, на сколько уменьшить (0 — снять целиком).
SHRINK_SCRIPT: Final = """
for i = 1, #KEYS do
  local entry = redis.call('HGET', KEYS[i], ARGV[1])
  if entry then
    local value, expires = string.match(entry, '^(%d+):(%d+)$')
    local left = tonumber(value) - tonumber(ARGV[2])
    if tonumber(ARGV[2]) == 0 or left <= 0 then
      redis.call('HDEL', KEYS[i], ARGV[1])
    else
      redis.call('HSET', KEYS[i], ARGV[1], string.format('%d:%s', left, expires))
    end
  end
end
return 1
"""
# KEYS: счётчики. ARGV: сумма, затем срок жизни каждого в мс.
COUNT_SCRIPT: Final = """
for i = 1, #KEYS do
  redis.call('INCRBY', KEYS[i], ARGV[1])
  redis.call('PEXPIRE', KEYS[i], ARGV[i + 1])
end
return 1
"""


def micro_usd(amount: Decimal) -> int:
    """Whole micro-USD, rounded up: a reservation never under-counts."""
    return int((amount * MICRO).to_integral_value(rounding=ROUND_CEILING))


@dataclass(frozen=True, slots=True)
class Counter:
    """One counter: its key, its reservations' key, how long it lives, what it limits."""

    key: str
    ttl: timedelta
    limit: SpendPeriod | str

    @property
    def held(self) -> str:
        """The key of the counter's live reservations."""
        return f"{self.key}:held"


def periods(at: datetime) -> dict[str, str]:
    """The UTC hour, day and month of a moment, as key parts."""
    moment = at.astimezone(UTC)
    return {"hour": moment.strftime("%Y%m%d%H"), "day": moment.strftime("%Y%m%d"),
            "month": moment.strftime("%Y%m")}  # fmt: skip


@dataclass(frozen=True, slots=True)
class Payer:
    """What decides a call's counters: who pays, how it was started, its class, its moment."""

    user_id: UUID | None
    platform_account: str | None
    origin: CallOrigin
    call_class: CallClass
    at: datetime


def counters_of(payer: Payer) -> list[Counter]:
    """The counters a call fills, each with the limit that may cap it."""
    when = periods(payer.at)
    found = [Counter(build_key("ai", "spend", "global", p, when[p]), TTLS[p], f"global_{p}")
             for p in ("hour", "day")]  # fmt: skip
    if payer.platform_account is not None:
        found += [
            Counter(build_key("ai", "spend", "platform", payer.platform_account, p, when[p]),
                    TTLS[p], f"platform_{p}")
            for p in ("hour", "day")
        ]  # fmt: skip
    if payer.user_id is None or payer.call_class is CallClass.ESSENTIAL:
        return found
    user = ("ai", "spend", "user", payer.user_id.hex)
    if payer.origin is CallOrigin.BACKGROUND:
        found.append(Counter(build_key(*user, "background", when["day"]), TTLS["day"],
                             SpendPeriod.BACKGROUND_DAY))  # fmt: skip
    elif payer.origin is CallOrigin.INTERACTIVE:
        found += [Counter(build_key(*user, p, when[p]), TTLS[p], SpendPeriod(p))
                  for p in ("hour", "day", "month")]  # fmt: skip
        if payer.call_class is CallClass.EXPENSIVE:
            found.append(Counter(build_key(*user, "expensive", when["month"]), TTLS["month"],
                                 SpendPeriod.EXPENSIVE_MONTH))  # fmt: skip
    return found
