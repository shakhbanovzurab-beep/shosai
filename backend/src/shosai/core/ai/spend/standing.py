"""Where the platform stands against its ceilings now, and OpenRouter's credit balance.

The platform's counters — global and per platform account, this hour and today — are read
from Valkey with their live reservations; the kill switch's state comes with them. The
balance is read from OpenRouter's `GET /credits`, which takes the management key, and is
kept 5 minutes; without that key the balance is unknown, not zero.
"""

import asyncio
import re
import time
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Final

import httpx
from redis.asyncio import Redis

from shosai.core.ai.adapters.http_calls import call_json
from shosai.core.ai.adapters.openrouter import OPENROUTER_API
from shosai.core.ai.calls import CallClass, CallOrigin, PlatformAccount, Provider
from shosai.core.ai.spend.counters import MICRO, Counter, Payer, counters_of
from shosai.core.ai.spend.guard import Ceilings
from shosai.core.ai.spend.kill_switch import KillSwitch, KillSwitchState
from shosai.core.kernel.business_calendar import BusinessCalendar

VALKEY_DEADLINE: Final = 1.0
CREDITS_TTL: Final = 300.0
HELD_ENTRY: Final = re.compile(r"(\d+):(\d+)")


@dataclass(frozen=True, slots=True)
class CeilingState:
    """One ceiling: what was recorded, what is reserved, and the ceiling, in USD."""

    name: str
    spent_usd: Decimal
    reserved_usd: Decimal
    ceiling_usd: Decimal


@dataclass(frozen=True, slots=True)
class Standing:
    """Every platform ceiling now, and the kill switch."""

    ceilings: tuple[CeilingState, ...]
    kill_switch: KillSwitchState


@dataclass(frozen=True, slots=True)
class Credits:
    """OpenRouter's credits bought and used, in USD."""

    total_usd: Decimal
    used_usd: Decimal

    @property
    def left_usd(self) -> Decimal:
        """What remains."""
        return self.total_usd - self.used_usd


class SpendStanding:
    """Reads the platform's counters against its ceilings."""

    def __init__(
        self, client: Redis, ceilings: Ceilings, kill_switch: KillSwitch, calendar: BusinessCalendar
    ) -> None:
        self._client = client
        self._calendar = calendar
        self._ceilings = ceilings
        self._kill_switch = kill_switch

    async def standing(self, at: datetime) -> Standing:
        """Global and platform-account ceilings this hour and this business day."""
        named: list[tuple[str, Counter, int]] = []
        for account in (None, *PlatformAccount):
            payer = Payer(None, account.value if account else None, CallOrigin.SYSTEM,
                          CallClass.STANDARD, at)  # fmt: skip
            for counter in counters_of(payer, self._calendar):
                name = (
                    str(counter.limit) if account is None else f"{account.value}_{counter.period}"
                )
                if account is None or str(counter.limit).startswith("platform"):
                    named.append((name, counter, self._ceiling(account, counter)))
        async with asyncio.timeout(VALKEY_DEADLINE):
            seconds, micros = await self._client.time()
            now_ms = seconds * 1000 + micros // 1000
            states = [await self._state(name, counter, ceiling, now_ms)
                      for name, counter, ceiling in named]  # fmt: skip
        return Standing(tuple(states), await self._kill_switch.state())

    async def _state(self, name: str, counter: Counter, ceiling: int, now_ms: int) -> CeilingState:
        spent = int(await self._client.get(counter.key) or 0)
        held = await self._client.hgetall(counter.held)
        reserved = 0
        for entry in held.values():
            text = entry.decode() if isinstance(entry, bytes) else str(entry)
            match = HELD_ENTRY.fullmatch(text)
            if match and int(match.group(2)) > now_ms:
                reserved += int(match.group(1))
        return CeilingState(name, Decimal(spent) / MICRO, Decimal(reserved) / MICRO,
                            Decimal(ceiling) / MICRO)  # fmt: skip

    def _ceiling(self, account: PlatformAccount | None, counter: Counter) -> int:
        if account is None:
            hour = counter.period == "hour"
            return self._ceilings.global_hour if hour else self._ceilings.global_day
        caps = self._ceilings.platform[account.value]
        return caps[0] if counter.period == "hour" else caps[1]


class OpenRouterCredits:
    """OpenRouter's balance through the management key, kept 5 minutes."""

    def __init__(self, client: httpx.AsyncClient | None) -> None:
        self._client = client
        self._kept: tuple[Credits, float] | None = None

    async def credits(self, *, fresh: bool = False) -> Credits | None:
        """The balance; None without the management key. `fresh` asks OpenRouter now, past
        the five minutes kept — the operator's connection check."""
        if self._client is None:
            return None
        kept = self._kept
        if not fresh and kept is not None and time.monotonic() - kept[1] < CREDITS_TTL:
            return kept[0]
        request = self._client.build_request("GET", "credits")
        answer = await call_json(self._client, Provider.OPENROUTER, request)
        raw = answer.get("data")
        data = raw if isinstance(raw, dict) else {}
        found = Credits(
            Decimal(str(data.get("total_credits") or 0)), Decimal(str(data.get("total_usage") or 0))
        )
        self._kept = (found, time.monotonic())
        return found


def management_client(key: str, base_url: str = OPENROUTER_API) -> httpx.AsyncClient:
    """A client of OpenRouter's management endpoints."""
    return httpx.AsyncClient(
        base_url=base_url.rstrip("/") + "/",
        headers={"Authorization": f"Bearer {key}"},
        timeout=httpx.Timeout(10.0),
    )
