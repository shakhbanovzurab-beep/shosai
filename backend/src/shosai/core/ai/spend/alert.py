"""The operator's alert on one user's AI spend today (F6-D6, §3.7).

After a commit writes a user's cost rows and the counters take them, the user's total today
is compared with `AI_USER_DAILY_ALERT_USD`. The first time it passes, an atomic `SET NX`
marker that lives to the end of the business day (ADR 0058) decides the one alert of that
user and day, and
the event `ai.user_spend.exceeded` is written to the outbox in its own small transaction in
the user's home — not in the cost row's transaction, which makes no external call (§14
rule 1). If that write fails, the marker is lifted and the next row tries again. The
marker holds this attempt's id, so the same holds when the check's answer came too late
to be read: only the attempt's own marker is lifted, never an earlier alert's.
"""

import asyncio
import secrets
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Final
from uuid import UUID

import structlog
from redis.asyncio import Redis

from shosai.core.ai.calls import CallClass, CallOrigin
from shosai.core.ai.costs.entries import CostEntry
from shosai.core.ai.events import UserSpendExceeded
from shosai.core.ai.spend.counters import Payer, counters_of
from shosai.core.db.errors import HomeUnavailableError
from shosai.core.db.transactions import HomeTransactions
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.business_calendar import BusinessCalendar
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.kv.connection import REDIS_FAILURES
from shosai.core.kv.keys import build_key
from shosai.core.kv.locks import RELEASE_SCRIPT
from shosai.core.observability.outage_log import OutageLog

VALKEY_DEADLINE: Final = 0.05
# KEYS: траты за день, метка. ARGV: порог, срок метки, id попытки. Ответ: траты, если
# тревога — эта.
ALERT_SCRIPT: Final = """
local total = tonumber(redis.call('GET', KEYS[1]) or '0')
if total < tonumber(ARGV[1]) then return 0 end
if redis.call('SET', KEYS[2], ARGV[3], 'NX', 'PX', ARGV[2]) then return total end
return 0
"""
log = structlog.stdlib.get_logger(__name__)


class SpendAlert:
    """Writes the one alert of a user and day when their spend passes the threshold."""

    def __init__(
        self,
        valkey: Redis,
        transactions: HomeTransactions,
        outbox: EventOutbox,
        threshold_micro: int,
        calendar: BusinessCalendar,
    ) -> None:
        self._calendar = calendar
        self._valkey = valkey
        self._check = valkey.register_script(ALERT_SCRIPT)
        self._lift = valkey.register_script(RELEASE_SCRIPT)
        self._transactions = transactions
        self._outbox = outbox
        self._threshold = threshold_micro
        self._outages = OutageLog("Valkey не ответил проверке трат пользователя")

    async def observe(self, entries: Sequence[CostEntry]) -> None:
        """Check each user of the rows a commit inserted; 0 as the threshold checks no one."""
        if not self._threshold:
            return
        users = {entry.user_id: entry for entry in entries if entry.user_id is not None}
        for user_id, entry in users.items():
            await self._checked(user_id, entry, datetime.now(UTC))

    async def _checked(self, user_id: UUID, entry: CostEntry, now: datetime) -> None:
        payer = Payer(user_id, None, CallOrigin.INTERACTIVE, CallClass.STANDARD, now)
        [total] = [c.key for c in counters_of(payer, self._calendar) if c.limit == "user_total_day"]
        day = self._calendar.date_of(now)
        marker = build_key("ai", "spend", "alerted", user_id.hex, f"{day:%Y%m%d}")
        _, day_end = self._calendar.day_window(now)
        ttl = int((day_end - now).total_seconds() * 1000) + 1
        attempt = secrets.token_hex(8)
        try:
            async with asyncio.timeout(VALKEY_DEADLINE):
                args: list[str | int] = [self._threshold, ttl, attempt]
                spend = int(await self._check(keys=[total, marker], args=args))
        except REDIS_FAILURES as error:
            self._outages.failed(error, operation="check")
            if isinstance(error, TimeoutError):
                # Скрипт мог отработать, а ответ — опоздать: метка без события съела бы сутки.
                await self._lifted(marker, attempt)
            return
        if not spend:
            return
        event = UserSpendExceeded(
            user_id=user_id, day=day, spend_micro_usd=spend,
            threshold_micro_usd=self._threshold,
        )  # fmt: skip
        scope = TenancyScope(entry.home, user_id, entry.org_id)
        try:
            async with self._transactions.begin(scope) as session:
                await self._outbox.add(session, event)
        except HomeUnavailableError:
            log.warning("Событие о тратах не записано: дом недоступен", home=entry.home.value)
            await self._lifted(marker, attempt)
            return
        log.info("Траты пользователя за сутки превысили порог", user_id=str(user_id))

    async def _lifted(self, marker: str, attempt: str) -> None:
        """Lift this attempt's marker so the next row tries again."""
        try:
            async with asyncio.timeout(VALKEY_DEADLINE):
                await self._lift(keys=[marker], args=[attempt])
        except REDIS_FAILURES as error:
            # Метка доживёт до конца суток: тревоги за эти сутки не будет, это видно в логе.
            self._outages.failed(error, operation="lift")
