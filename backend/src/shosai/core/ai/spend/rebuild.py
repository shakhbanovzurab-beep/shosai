"""The spend counters rebuilt from the cost rows, after Valkey came back empty (F6-D8).

The counters live in Valkey; `provider_costs` is the record. When Valkey lost its data — or
at cutover (DATA_MAPPING E-3) — the counters of the current hour, day and month are summed
again from the rows of both homes, each row counted as the writer counts it (its cost in
micro-USD rounded up, into the same counters). The global counters span both homes, so
both are read before anything is written. Reservations are not rebuilt: they are leased.

Rows keep being recorded while the rebuild runs, and the writer counts a row only after
its commit. Each row must reach the counters exactly once, so:

1. The rebuild sets a mark in Valkey. While it stands, the writer's count script also puts
   the row — its id, payer and amount — on a waiting list.
2. One statement per home reads the sums and, in the same snapshot, which waiting rows it
   already holds; the waiting rows it does not hold are added to the sums.
3. One script writes the counters, empties the list and lifts the mark — unless the list
   grew since it was read, and then the rebuild reads again.

If the rebuild fails, it lifts the mark: the writer kept counting all along, so the counters
are as they were before it started.
"""

import secrets
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any, Final
from uuid import UUID

import structlog
from redis.asyncio import Redis
from sqlalchemy import Select, func, select, true

from shosai.core.ai.calls import CallClass, CallOrigin
from shosai.core.ai.costs.records import ProviderCost
from shosai.core.ai.spend.counters import (
    REBUILD_MARK,
    REBUILD_PENDING,
    REBUILD_SCRIPT,
    Payer,
    counters_of,
    pending_payer,
    periods,
)
from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.business_calendar import BusinessCalendar
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope

MICRO_FACTOR: Final = 1_000_000
MARK_TTL: Final = timedelta(minutes=10)
ATTEMPTS: Final = 20
log = structlog.stdlib.get_logger(__name__)


class RebuildBusyError(Exception):
    """Another rebuild holds the mark."""


class RebuildUnsettledError(Exception):
    """Rows kept arriving faster than the rebuild could read them; nothing was written."""


def text_of(value: bytes | str) -> str:
    """A Valkey reply as text."""
    return value.decode() if isinstance(value, bytes) else value


class CounterRebuild:
    """One rebuild: mark, read, write; the mark is lifted however it ends."""

    def __init__(
        self,
        transactions: HomeTransactions,
        valkey: Redis,
        at: datetime,
        business: BusinessCalendar,
    ) -> None:
        self._transactions = transactions
        self._valkey = valkey
        self._now = at.astimezone(UTC)
        self._business = business
        self._id = secrets.token_hex(12)
        self._write = valkey.register_script(REBUILD_SCRIPT)

    async def start(self) -> None:
        """Set the mark; from now on the rows counted wait on the list."""
        ttl = int(MARK_TTL.total_seconds() * 1000)
        if not await self._valkey.set(REBUILD_MARK, self._id, nx=True, px=ttl):
            raise RebuildBusyError

    async def finish(self) -> int:
        """Read and write until the waiting list holds still; return the counters written."""
        try:
            for _ in range(ATTEMPTS):
                waiting = {
                    text_of(k): v for k, v in (await self._valkey.hgetall(REBUILD_PENDING)).items()
                }
                sums, ttls = await self._summed(waiting)
                keys = sorted(sums)
                args: list[str | int] = [self._id, len(waiting), *(sums[k] for k in keys),
                                         *(ttls[k] for k in keys)]  # fmt: skip
                written = int(
                    await self._write(keys=[REBUILD_MARK, REBUILD_PENDING, *keys], args=args)
                )
                if written == -2:
                    raise RebuildBusyError
                if written >= 0:
                    log.warning(
                        "Счётчики расходов пересобраны по строкам стоимости", counters=written
                    )
                    return written
            raise RebuildUnsettledError
        except BaseException:
            await self._lifted()
            raise

    async def _summed(self, waiting: Mapping[str, Any]) -> tuple[dict[str, int], dict[str, int]]:
        sums: dict[str, int] = defaultdict(int)
        ttls: dict[str, int] = {}
        held: set[UUID] = set()
        statement = self._statement([UUID(hex=key) for key in waiting])
        for home in Home:
            async with self._transactions.begin(TenancyScope(home), read_only=True) as session:
                for found, user, account, origin, call_class, hour, amount in (
                    await session.execute(statement)
                ).all():
                    held |= set(found or ())
                    if amount is not None:
                        payer = Payer(
                            user, account, CallOrigin(origin), CallClass(call_class), hour
                        )
                        self._add(payer, int(amount), sums, ttls)
        for key, raw in waiting.items():
            if UUID(hex=key) not in held:
                payer, amount = pending_payer(raw)
                self._add(payer, amount, sums, ttls)
        return sums, ttls

    def _add(self, payer: Payer, amount: int, sums: dict[str, int], ttls: dict[str, int]) -> None:
        current = periods(self._now, self._business)
        for counter in counters_of(payer, self._business):
            if counter.key.endswith(f":{current[counter.period]}"):
                sums[counter.key] += amount
                ttls[counter.key] = int(counter.ttl.total_seconds() * 1000)

    def _statement(self, ids: Sequence[UUID]) -> Select[Any]:
        """Sums of the periods and the waiting rows the home holds, in one snapshot."""
        hour = func.date_trunc("hour", ProviderCost.created_at, "UTC")
        columns = (ProviderCost.user_id, ProviderCost.platform_account, ProviderCost.origin,
                   ProviderCost.call_class, hour)  # fmt: skip
        month, _ = self._business.month_window(self._now)
        since = min(month, self._now - timedelta(days=1))
        sums = (
            select(*columns, func.sum(func.ceil(ProviderCost.cost_usd * MICRO_FACTOR)))
            .where(ProviderCost.created_at >= since)
            .group_by(*columns)
            .subquery()
        )
        found = (
            select(func.array_agg(ProviderCost.id).label("found"))
            .where(ProviderCost.id.in_(ids))
            .subquery()
        )
        # Внешнее соединение с одной строкой найденных: ответ есть и при пустом месяце.
        return select(found.c.found, *sums.c).select_from(found.outerjoin(sums, true()))

    async def _lifted(self) -> None:
        """Lift this rebuild's mark and its waiting list."""
        if await self._valkey.get(REBUILD_MARK) == self._id.encode():
            await self._valkey.delete(REBUILD_MARK, REBUILD_PENDING)


async def rebuild_spend_counters(
    transactions: HomeTransactions, valkey: Redis, at: datetime, business: BusinessCalendar
) -> int:
    """Rewrite the current counters from the rows of both homes; return how many."""
    rebuild = CounterRebuild(transactions, valkey, at, business)
    await rebuild.start()
    return await rebuild.finish()
