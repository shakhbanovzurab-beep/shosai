"""The operator's `platform` toolset: the platform's own numbers (ADR 0068 AG-D5; agent step 16).

What platform services already serve their operator is read here for Leo in the admin panel:
AI spend from F6's reports — a summary by provider, model or feature, each day of a period, the
month's forecast — the OpenRouter balance, and the counts of the ratings of Leo's answers.
Every result names its report as a source, so the answer cites it. No tool reads a person's
content or changes anything, and each refuses any caller but the platform operator, whatever
offered it. Other owners add their aggregates to this toolset in their own slices.
"""

from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from shosai.core.agent_tools.bindings import AgentTool, ReadTool, RunHandler
from shosai.core.agent_tools.context import ToolContext
from shosai.core.agent_tools.results import ToolErrorCode, ToolResult
from shosai.core.agent_tools.sources import SourceKind, SourceRef
from shosai.core.agent_tools.spec import ToolEffect, ToolSpec
from shosai.core.ai.spend.operator import SpendOperator
from shosai.core.ai.spend.reports import ReportPeriod, SummaryGroup
from shosai.features.agent.application.platform_ratings import PlatformRatings
from shosai.features.agent.domain.operator import PLATFORM_TOOLSET, is_operator

CENTS: Final = Decimal("0.01")
TIMEOUT: Final = timedelta(seconds=20)
TOP_MODELS: Final = 5


class Strict(BaseModel):
    """Arguments the model may not add to."""

    model_config = ConfigDict(extra="forbid")


class SpendSummaryIn(Strict):
    """Which spend to sum up."""

    period: Literal["today", "month", "all_time"] = Field(
        description="today, this month, or all time (business calendar)."
    )
    group: Literal["provider", "model", "feature"] = Field(description="What to group by.")


class SpendLine(BaseModel):
    """One group's spend."""

    key: str
    calls: int
    cost_usd: float
    cost_rub: float


class SpendSummaryOut(BaseModel):
    """AI spend of both homes, the largest first."""

    total_usd: float
    rows: list[SpendLine]


class DaysIn(Strict):
    """How far back to look."""

    days: int = Field(default=30, ge=1, le=90, description="The last N days, today included.")


class SpendDay(BaseModel):
    """One day's spend over every model."""

    day: str
    calls: int
    cost_usd: float


class SpendDailyOut(BaseModel):
    """Each day's AI spend, oldest first, and the models that cost the most over the period."""

    days: list[SpendDay]
    top_models: list[SpendLine]


class NothingIn(Strict):
    """No arguments."""


class ForecastOut(BaseModel):
    """The month so far and where it ends at the same pace, in USD."""

    month_to_date_usd: float
    projected_usd: float
    elapsed_days: float
    days_in_month: int


class BalanceOut(BaseModel):
    """OpenRouter's credits, in USD."""

    total_usd: float
    used_usd: float
    left_usd: float


class RatingLine(BaseModel):
    """How a model's answers were rated."""

    model: str
    useful: int
    not_useful: int


class RatingsOut(BaseModel):
    """Ratings of Leo's answers over the period, counts only."""

    useful: int
    not_useful: int
    by_model: list[RatingLine]


def platform_spec[I: BaseModel, O: BaseModel](
    name: str, description: str, models: tuple[type[I], type[O]], detail: str | None = None
) -> ToolSpec[I, O]:
    """A read of the platform's numbers."""
    return ToolSpec(
        name=f"{PLATFORM_TOOLSET}.{name}", toolset=PLATFORM_TOOLSET, description=description,
        input=models[0], output=models[1], effect=ToolEffect.READ, timeout=TIMEOUT,
        step_detail=detail,
    )  # fmt: skip


SPEND_SUMMARY: Final = platform_spec(
    "spend_summary",
    "AI spend of the whole platform (both homes) for today, this month or all time, grouped "
    "by provider, model or feature, in USD and RUB.",
    (SpendSummaryIn, SpendSummaryOut), "period",
)  # fmt: skip
SPEND_DAILY: Final = platform_spec(
    "spend_daily",
    "AI spend of the whole platform for each of the last N days, and the costliest models.",
    (DaysIn, SpendDailyOut),
)
SPEND_FORECAST: Final = platform_spec(
    "spend_forecast",
    "This month's AI spend so far and where the month ends at the same pace.",
    (NothingIn, ForecastOut),
)
OPENROUTER_BALANCE: Final = platform_spec(
    "openrouter_balance", "OpenRouter's credits: bought, used and left.", (NothingIn, BalanceOut)
)
ANSWER_RATINGS: Final = platform_spec(
    "answer_ratings",
    "How people rated Leo's answers (useful or not) over the last N days, by model; counts only.",
    (DaysIn, RatingsOut),
)
PLATFORM_TOOLS: Final = (
    SPEND_SUMMARY,
    SPEND_DAILY,
    SPEND_FORECAST,
    OPENROUTER_BALANCE,
    ANSWER_RATINGS,
)


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


def operator_only[I: BaseModel, O: BaseModel](run: RunHandler[I, O]) -> RunHandler[I, O]:
    """The handler, for the operator alone: anyone else is refused, whatever offered it."""

    async def guarded(arguments: I, context: ToolContext) -> ToolResult[O]:
        if not is_operator(context.scope.user_id):
            return ToolResult.failed(ToolErrorCode.FORBIDDEN)
        return await run(arguments, context)

    return guarded


class PlatformReads:
    """The platform's numbers for the operator, from F6's reports and the ratings' counts."""

    def __init__(
        self,
        spend: SpendOperator,
        ratings: PlatformRatings,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._spend, self._ratings, self._clock = spend, ratings, clock

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
        title = f"AI spend, {arguments.period}, by {arguments.group}"
        source = report(f"spend.summary:{arguments.period}:{arguments.group}", title)
        return ToolResult(SpendSummaryOut(total_usd=total, rows=lines), sources=source)

    async def spend_daily(self, arguments: DaysIn, context: ToolContext) -> ToolResult[Any]:
        """Each day's spend over every model, and the costliest models of the period."""
        del context
        rows = await self._spend.reports.daily(self._clock(), arguments.days)
        days: dict[str, list[Decimal]] = defaultdict(lambda: [Decimal(0), Decimal(0)])
        models: dict[str, list[Decimal]] = defaultdict(lambda: [Decimal(0), Decimal(0)])
        for row in rows:
            for bucket in (days[row.day.isoformat()], models[row.model]):
                bucket[0] += row.calls
                bucket[1] += row.cost_usd
        costliest = sorted(models.items(), key=lambda item: item[1][1], reverse=True)[:TOP_MODELS]
        output = SpendDailyOut(
            days=[SpendDay(day=d, calls=int(v[0]), cost_usd=usd(v[1]))
                  for d, v in sorted(days.items())],
            top_models=[SpendLine(key=m, calls=int(v[0]), cost_usd=usd(v[1]), cost_rub=0.0)
                        for m, v in costliest],
        )  # fmt: skip
        title = f"AI spend per day, last {arguments.days} days"
        return ToolResult(output, sources=report(f"spend.daily:{arguments.days}", title))

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
        title = f"Ratings of Leo's answers, last {arguments.days} days"
        return ToolResult(output, sources=report(f"ratings:{arguments.days}", title))


def platform_tools(reads: PlatformReads) -> tuple[AgentTool, ...]:
    """The toolset bound to the operator's reads, each for the operator alone."""
    handlers: tuple[tuple[ToolSpec[Any, Any], RunHandler[Any, Any]], ...] = (
        (SPEND_SUMMARY, reads.spend_summary), (SPEND_DAILY, reads.spend_daily),
        (SPEND_FORECAST, reads.spend_forecast), (OPENROUTER_BALANCE, reads.openrouter_balance),
        (ANSWER_RATINGS, reads.answer_ratings),
    )  # fmt: skip
    return tuple(ReadTool(spec, operator_only(run)) for spec, run in handlers)
