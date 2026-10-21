"""Spend reports for the operator's screens: both homes, USD and RUB (§3.6, F6-D5).

Application services, not routes: `studio`'s AI models screen and `identity`'s account card
call them from their own admin routers. Every report reads `provider_costs` of both homes
and adds them up; rubles are the sum of each row's own rubles, at the rate of its moment,
and the rows written without a rate are counted apart. Days, weeks and months are the
business calendar's (ADR 0058), like the counters'.
"""

from calendar import monthrange
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Any, Final
from uuid import UUID

from sqlalchemy import Select, func, select

from shosai.core.ai.costs.records import ProviderCost
from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.business_calendar import BusinessCalendar
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope

ZERO: Final = Decimal(0)
SHORTEST_ELAPSED: Final = timedelta(hours=1)


class SummaryGroup(StrEnum):
    """What a summary is grouped by."""

    PROVIDER = "provider"
    MODEL = "model"
    FEATURE = "feature"


class ReportPeriod(StrEnum):
    """Which rows a summary adds up."""

    TODAY = "today"
    MONTH = "month"
    ALL_TIME = "all_time"


@dataclass(frozen=True, slots=True)
class SummaryRow:
    """One group's calls and money; `without_rate` rows have USD but no rubles."""

    key: str
    calls: int
    cost_usd: Decimal
    cost_rub: Decimal
    without_rate: int


@dataclass(frozen=True, slots=True)
class DailyRow:
    """One model's day: calls, tokens and money."""

    day: date
    provider: str
    model: str
    calls: int
    input_tokens: int
    output_tokens: int
    audio_tokens: int
    cost_usd: Decimal


@dataclass(frozen=True, slots=True)
class Forecast:
    """The month so far and where it ends at the same pace."""

    month_to_date_usd: Decimal
    projected_usd: Decimal
    elapsed_days: Decimal
    days_in_month: int


@dataclass(frozen=True, slots=True)
class UserSpend:
    """One person's AI spend: today, this ISO week and this month, in USD."""

    today_usd: Decimal
    week_usd: Decimal
    month_usd: Decimal


class SpendReports:
    """Reports over the cost rows of both homes, by the business calendar's periods."""

    def __init__(self, transactions: HomeTransactions, business: BusinessCalendar) -> None:
        self._transactions = transactions
        self._business = business

    async def summary(
        self, group: SummaryGroup, period: ReportPeriod, at: datetime
    ) -> tuple[SummaryRow, ...]:
        """Calls and money per provider, model or feature, the largest spend first."""
        column = getattr(ProviderCost, group.value)
        statement = select(
            column, func.count(), func.sum(ProviderCost.cost_usd),
            func.sum(ProviderCost.cost_rub), func.count() - func.count(ProviderCost.cost_rub),
        ).group_by(column)  # fmt: skip
        if period is ReportPeriod.TODAY:
            statement = statement.where(ProviderCost.created_at >= self._business.day_window(at)[0])
        elif period is ReportPeriod.MONTH:
            month, _ = self._business.month_window(at)
            statement = statement.where(ProviderCost.created_at >= month)
        totals: dict[str, list[Any]] = {}
        for key, calls, usd, rub, unrated in await self._both(statement):
            row = totals.setdefault(str(key), [0, ZERO, ZERO, 0])
            row[0] += calls
            row[1] += usd or ZERO
            row[2] += rub or ZERO
            row[3] += unrated
        rows = [SummaryRow(key, *values) for key, values in totals.items()]
        return tuple(sorted(rows, key=lambda row: row.cost_usd, reverse=True))

    async def daily(self, at: datetime, days: int = 30) -> tuple[DailyRow, ...]:
        """Each model's days over the last `days`, oldest first."""
        # Сутки делового пояса, как у счётчиков, а не по часовому поясу сеанса базы.
        zone = self._business.zone
        day = func.date_trunc("day", ProviderCost.created_at, self._business.zone_name)
        first = self._business.midnight(self._business.date_of(at) - timedelta(days=days - 1))
        statement = (
            select(
                day,
                ProviderCost.provider,
                ProviderCost.model,
                func.count(),
                func.sum(ProviderCost.input_tokens),
                func.sum(ProviderCost.output_tokens),
                func.sum(ProviderCost.input_audio_tokens + ProviderCost.output_audio_tokens),
                func.sum(ProviderCost.cost_usd),
            )
            .where(ProviderCost.created_at >= first)
            .group_by(day, ProviderCost.provider, ProviderCost.model)
        )
        totals: dict[tuple[date, str, str], list[Any]] = {}
        for moment, provider, model, *numbers in await self._both(statement):
            key = (moment.astimezone(zone).date(), provider, model)
            row = totals.setdefault(key, [0, 0, 0, 0, ZERO])
            for index, number in enumerate(numbers):
                row[index] += number or 0
        return tuple(DailyRow(*key, *values) for key, values in sorted(totals.items()))

    async def forecast(self, at: datetime) -> Forecast:
        """The month to date, and the month's end at the pace of the days elapsed."""
        start, _ = self._business.month_window(at)
        statement = select(func.sum(ProviderCost.cost_usd)).where(ProviderCost.created_at >= start)
        so_far = sum((usd or ZERO for (usd,) in await self._both(statement)), ZERO)
        elapsed = max(at - start, SHORTEST_ELAPSED)
        elapsed_days = Decimal(elapsed.total_seconds()) / Decimal(86_400)
        length = monthrange(start.year, start.month)[1]
        projected = (so_far / elapsed_days * length).quantize(Decimal("0.01"))
        return Forecast(so_far, projected, elapsed_days.quantize(Decimal("0.001")), length)

    async def user_spend(self, home: Home, user_id: UUID, at: datetime) -> UserSpend:
        """One person's spend from their home's rows."""
        today, _ = self._business.day_window(at)
        week, _ = self._business.week_window(at)
        month, _ = self._business.month_window(at)
        usd = ProviderCost.cost_usd
        statement = select(
            func.sum(usd).filter(ProviderCost.created_at >= today),
            func.sum(usd).filter(ProviderCost.created_at >= week),
            func.sum(usd).filter(ProviderCost.created_at >= month),
        ).where(ProviderCost.user_id == user_id, ProviderCost.created_at >= min(week, month))
        async with self._transactions.begin(TenancyScope(home), read_only=True) as session:
            row = (await session.execute(statement)).one()
        return UserSpend(*(value or ZERO for value in row))

    async def _both(self, statement: Select[Any]) -> Sequence[Any]:
        """The statement's rows from the RU home, then the EU home."""
        rows: list[Any] = []
        for home in Home:
            async with self._transactions.begin(TenancyScope(home), read_only=True) as session:
                rows += (await session.execute(statement)).all()
        return rows
