"""The operator's `platform` toolset as the model sees it: arguments, results and specs (AG-D5).

Each tool reads one aggregate the platform already serves its operator — AI spend, the
OpenRouter balance, answer ratings, plans and promo codes, account counts — never a person's
content, and changes nothing.
"""

from datetime import timedelta
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from shosai.core.agent_tools.spec import ToolEffect, ToolSpec
from shosai.features.agent.domain.operator import PLATFORM_TOOLSET

TIMEOUT: Final = timedelta(seconds=20)


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


class PlanLine(BaseModel):
    """A plan of the catalogue: prices per currency in major units, and its subscribers."""

    slug: str
    name: str
    audience: str
    subscribers: int
    on_sale: bool
    archived: bool
    month_prices: dict[str, float]
    year_prices: dict[str, float]


class PlansOut(BaseModel):
    """Every plan, archived ones included, in the pricing page's order."""

    plans: list[PlanLine]


class PromoLine(BaseModel):
    """A promo code with its status today."""

    code: str
    status: str
    percent_off: int | None
    redemptions: int
    max_redemptions: int | None
    valid_until: str | None


class PromoCodesOut(BaseModel):
    """Every promo code, newest first."""

    promo_codes: list[PromoLine]


class HomeLine(BaseModel):
    """One data home's accounts: by state, and those registered in the period."""

    home: str
    by_state: dict[str, int]
    registered: int


class AccountsOut(BaseModel):
    """Accounts of both data homes, counts only."""

    homes: list[HomeLine]


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
PLANS: Final = platform_spec(
    "plans",
    "The plans of the catalogue with their prices and how many subscribe to each.",
    (NothingIn, PlansOut),
)
PROMO_CODES: Final = platform_spec(
    "promo_codes",
    "Every promo code with its discount, use and status today.",
    (NothingIn, PromoCodesOut),
)
ACCOUNTS: Final = platform_spec(
    "accounts",
    "How many accounts each data home holds, by state, and how many registered in the last "
    "N days; counts only.",
    (DaysIn, AccountsOut),
)
PLATFORM_TOOLS: Final = (
    SPEND_SUMMARY, SPEND_DAILY, SPEND_FORECAST, OPENROUTER_BALANCE, ANSWER_RATINGS, PLANS,
    PROMO_CODES, ACCOUNTS,
)  # fmt: skip
