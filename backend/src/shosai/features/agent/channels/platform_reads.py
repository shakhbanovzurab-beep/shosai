"""The platform's numbers for the operator's Leo, with their reports and charts (AG-D5, AG-D10).

AI spend comes from F6's reports and balance, plans and promo codes from billing's
`CommerceFacts`, account counts from identity's `AccountCounts`, and ratings from the agent's
own read-only count. Each result names its report as its source; a result that is a series —
spend per group or per day, ratings per model, accounts per home, subscribers per plan — also
hands the cabinet a chart of it, computed here from the same rows.
"""

from collections import defaultdict
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Final

from pydantic import JsonValue

from shosai.core.agent_tools.context import ToolContext
from shosai.core.agent_tools.results import ToolErrorCode, ToolResult
from shosai.core.agent_tools.sources import SourceKind, SourceRef
from shosai.core.ai.spend.operator import SpendOperator
from shosai.core.ai.spend.reports import ReportPeriod, SummaryGroup
from shosai.core.ports.directory import PortDirectory
from shosai.features.agent.application.platform_ratings import PlatformRatings
from shosai.features.agent.channels.platform_specs import (
    AccountsOut,
    BalanceOut,
    DaysIn,
    ForecastOut,
    HomeLine,
    NothingIn,
    PlanLine,
    PlansOut,
    PromoCodesOut,
    PromoLine,
    RatingLine,
    RatingsOut,
    SpendDailyOut,
    SpendDay,
    SpendLine,
    SpendSummaryIn,
    SpendSummaryOut,
)  # fmt: skip
from shosai.features.agent.domain.charts import Series, chart
from shosai.features.billing.contracts import COMMERCE_FACTS
from shosai.features.identity.contracts.accounts import ACCOUNT_COUNTS

CENTS: Final = Decimal("0.01")
TOP_MODELS: Final = 5
MINOR: Final = 100
# Подписи графиков — для админ-панели, которая только на русском (docs/i18n.md).
PERIODS: Final[Mapping[str, str]] = {
    "today": "сегодня",
    "month": "этот месяц",
    "all_time": "всё время",
}
GROUPS: Final[Mapping[str, str]] = {
    "provider": "провайдерам",
    "model": "моделям",
    "feature": "функциям",
}
USD: Final = Series("cost_usd", "USD")


class Rating(StrEnum):
    """The two ratings, as `agent_feedback` keeps them."""

    USEFUL = "useful"
    NOT_USEFUL = "not_useful"


def usd(value: Decimal) -> float:
    """Money to the cent."""
    return float(value.quantize(CENTS))


def report(report_id: str, title: str) -> tuple[SourceRef, ...]:
    """The report a result rests on, as its one source."""
    return (SourceRef(SourceKind.REPORT, report_id, title),)


def major(prices: Mapping[str, int]) -> dict[str, float]:
    """Prices in minor units as major ones: all three currencies have cents."""
    return {currency: amount / MINOR for currency, amount in prices.items()}


class PlatformReads:
    """The platform's numbers for the operator."""

    def __init__(
        self,
        sources: tuple[SpendOperator, PlatformRatings, PortDirectory],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._spend, self._ratings, self._ports = sources
        self._clock = clock

    async def spend_summary(
        self, arguments: SpendSummaryIn, context: ToolContext
    ) -> ToolResult[Any]:
        """The spend of a period by provider, model or feature."""
        del context
        rows = await self._spend.reports.summary(
            SummaryGroup(arguments.group), ReportPeriod(arguments.period), self._clock()
        )
        lines = [SpendLine(key=r.key, calls=r.calls, cost_usd=usd(r.cost_usd),
                           cost_rub=usd(r.cost_rub)) for r in rows]  # fmt: skip
        total = usd(sum((r.cost_usd for r in rows), Decimal(0)))
        report_id = f"spend.summary:{arguments.period}:{arguments.group}"
        title = f"Расходы на ИИ, {PERIODS[arguments.period]}, по {GROUPS[arguments.group]}"
        drawn = chart(report_id, title, ("bar", "key", (USD,)),
                      [{"key": line.key, "cost_usd": line.cost_usd} for line in lines])  # fmt: skip
        source = report(report_id, f"AI spend, {arguments.period}, by {arguments.group}")
        output = SpendSummaryOut(total_usd=total, rows=lines)
        return ToolResult(output, sources=source, artifacts=drawn)

    async def spend_daily(self, arguments: DaysIn, context: ToolContext) -> ToolResult[Any]:
        """Each day's spend over every model, and the costliest models of the period."""
        del context
        at = self._clock()
        rows = await self._spend.reports.daily(at, arguments.days)
        # Каждый день периода, и день без вызовов — нулём: ось времени графика не пропускает дней.
        days = {
            day.isoformat(): [Decimal(0), Decimal(0)]
            for day in self._spend.reports.days(at, arguments.days)
        }
        models: dict[str, list[Decimal]] = defaultdict(lambda: [Decimal(0), Decimal(0)])
        for row in rows:
            zero = [Decimal(0), Decimal(0)]
            for bucket in (days.setdefault(row.day.isoformat(), zero), models[row.model]):
                bucket[0] += row.calls
                bucket[1] += row.cost_usd
        costliest = sorted(models.items(), key=lambda item: item[1][1], reverse=True)[:TOP_MODELS]
        output = SpendDailyOut(
            days=[SpendDay(day=d, calls=int(v[0]), cost_usd=usd(v[1]))
                  for d, v in sorted(days.items())],
            top_models=[SpendLine(key=m, calls=int(v[0]), cost_usd=usd(v[1]), cost_rub=0.0)
                        for m, v in costliest],
        )  # fmt: skip
        report_id = f"spend.daily:{arguments.days}"
        heading = f"Расходы на ИИ по дням, {arguments.days} дн."
        drawn = chart(report_id, heading, ("line", "day", (USD,)),
                      [{"day": d.day, "cost_usd": d.cost_usd} for d in output.days])  # fmt: skip
        title = f"AI spend per day, last {arguments.days} days"
        return ToolResult(output, sources=report(report_id, title), artifacts=drawn)

    async def spend_forecast(self, arguments: NothingIn, context: ToolContext) -> ToolResult[Any]:
        """The month so far and its end at the same pace."""
        del arguments, context
        found = await self._spend.reports.forecast(self._clock())
        output = ForecastOut(
            month_to_date_usd=usd(found.month_to_date_usd), projected_usd=usd(found.projected_usd),
            elapsed_days=float(found.elapsed_days), days_in_month=found.days_in_month,
        )  # fmt: skip
        return ToolResult(output, sources=report("spend.forecast", "AI spend forecast, this month"))

    async def openrouter_balance(
        self, arguments: NothingIn, context: ToolContext
    ) -> ToolResult[Any]:
        """OpenRouter's credits; unavailable without the management key."""
        del arguments, context
        credits = await self._spend.credits.credits()
        if credits is None:
            return ToolResult.failed(ToolErrorCode.UNAVAILABLE)
        output = BalanceOut(
            total_usd=usd(credits.total_usd), used_usd=usd(credits.used_usd),
            left_usd=usd(credits.left_usd),
        )  # fmt: skip
        return ToolResult(output, sources=report("openrouter.balance", "OpenRouter credits"))

    async def answer_ratings(self, arguments: DaysIn, context: ToolContext) -> ToolResult[Any]:
        """The ratings of the period, by model."""
        del context
        found = await self._ratings.counts(arguments.days)
        lines = [
            RatingLine(model=m, useful=found.by_model.get((m, Rating.USEFUL), 0),
                       not_useful=found.by_model.get((m, Rating.NOT_USEFUL), 0))
            for m in sorted({model for model, _ in found.by_model})
        ]  # fmt: skip
        output = RatingsOut(
            useful=found.by_rating.get(Rating.USEFUL, 0),
            not_useful=found.by_rating.get(Rating.NOT_USEFUL, 0),
            by_model=lines,
        )
        report_id = f"ratings:{arguments.days}"
        series = (Series("useful", "Полезно"), Series("not_useful", "Бесполезно"))
        heading = f"Оценки ответов Leo, {arguments.days} дн."
        drawn = chart(report_id, heading, ("bar", "model", series),
                      [line.model_dump() for line in lines], stacked=True)  # fmt: skip
        title = f"Ratings of Leo's answers, last {arguments.days} days"
        return ToolResult(output, sources=report(report_id, title), artifacts=drawn)

    async def plans(self, arguments: NothingIn, context: ToolContext) -> ToolResult[Any]:
        """The catalogue's plans with their prices and subscribers."""
        del arguments, context
        found = await self._ports.get(COMMERCE_FACTS).plans()
        lines = [
            PlanLine(slug=p.slug, name=p.name, audience=p.audience, subscribers=p.subscribers,
                     on_sale=p.on_sale, archived=p.archived, month_prices=major(p.month_prices),
                     year_prices=major(p.year_prices))
            for p in found
        ]  # fmt: skip
        rows: list[dict[str, JsonValue]] = [
            {"name": line.name, "subscribers": line.subscribers} for line in lines
        ]
        drawn = chart("billing.plans", "Подписчики по тарифам",
                      ("bar", "name", (Series("subscribers", "Подписчики"),)), rows)  # fmt: skip
        source = report("billing.plans", "Plans and subscribers")
        return ToolResult(PlansOut(plans=lines), sources=source, artifacts=drawn)

    async def promo_codes(self, arguments: NothingIn, context: ToolContext) -> ToolResult[Any]:
        """Every promo code with its status today."""
        del arguments, context
        found = await self._ports.get(COMMERCE_FACTS).promo_codes()
        lines = [
            PromoLine(code=c.code, status=c.status, percent_off=c.percent_off,
                      redemptions=c.redemptions, max_redemptions=c.max_redemptions,
                      valid_until=c.valid_until.isoformat() if c.valid_until else None)
            for c in found
        ]  # fmt: skip
        return ToolResult(
            PromoCodesOut(promo_codes=lines), sources=report("billing.promo_codes", "Promo codes")
        )

    async def accounts(self, arguments: DaysIn, context: ToolContext) -> ToolResult[Any]:
        """Each data home's accounts by state, and those registered in the period."""
        del context
        found = await self._ports.get(ACCOUNT_COUNTS).counts(arguments.days)
        lines = [HomeLine(home=h.home.value, by_state=dict(h.by_state), registered=h.registered)
                 for h in found]  # fmt: skip
        series = (
            Series("active", "Активные"),
            Series("registered", f"Новые за {arguments.days} дн."),
        )
        drawn = chart(f"identity.accounts:{arguments.days}", "Аккаунты по домам данных",
                      ("bar", "home", series),
                      [{"home": line.home.upper(), "active": line.by_state.get("active", 0),
                        "registered": line.registered} for line in lines])  # fmt: skip
        title = f"Accounts by data home, last {arguments.days} days"
        source = report(f"identity.accounts:{arguments.days}", title)
        return ToolResult(AccountsOut(homes=lines), sources=source, artifacts=drawn)
