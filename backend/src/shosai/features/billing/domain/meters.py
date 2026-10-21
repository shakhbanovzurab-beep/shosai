"""The usage windows and allowances: minutes a month, tokens a week (BL-D3, BL-D4).

Minutes reset on the first day of a month, tokens on Monday at midnight, both in the
business time zone (ADR 0058, `BusinessCalendar`). Minutes are
counted in seconds and judged on the raw total, never on a rounded remainder. A frontier
request past its weekly allowance spends packs, then falls back to a standard model; a
standard request past the plan's daily tokens stops with its reason (BL-D4).
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from shosai.core.kernel.business_calendar import BusinessCalendar
from shosai.features.billing.domain.plans import ModelTier

SECONDS_IN_MINUTE = 60


def tombstones_since(now: datetime, business: BusinessCalendar) -> datetime:
    """The earliest meeting start whose tombstone still matters: the previous month's start.

    A meeting deleted late may still fall into last month; older months count no more.
    """
    start, _ = business.month_window(now)
    previous, _ = business.month_window(start - timedelta(microseconds=1))
    return previous


@dataclass(frozen=True, slots=True)
class MinutesLeft:
    """A month's meeting minutes: the plan's limit (None: unlimited) and the seconds used."""

    limit_minutes: int | None
    used_seconds: int

    @property
    def exhausted(self) -> bool:
        """The month's minutes are used up."""
        return (
            self.limit_minutes is not None
            and self.used_seconds >= self.limit_minutes * SECONDS_IN_MINUTE
        )

    @property
    def remaining_minutes(self) -> int | None:
        """Whole minutes left, never below zero; None when unlimited."""
        if self.limit_minutes is None:
            return None
        left = self.limit_minutes * SECONDS_IN_MINUTE - self.used_seconds
        return max(left, 0) // SECONDS_IN_MINUTE

    def covers(self, seconds: int) -> bool:
        """Whether a recording this long fits what is left (an upload's pre-check)."""
        if self.limit_minutes is None:
            return True
        return self.used_seconds + seconds <= self.limit_minutes * SECONDS_IN_MINUTE


class TokenRoute(StrEnum):
    """What a model request does with the person's tokens."""

    WITHIN_ALLOWANCE = "within_allowance"
    FROM_PACKS = "from_packs"
    # Frontier исчерпан вместе с пакетами: отвечает стандартная модель, с пометкой под ответом.
    FALL_BACK = "fall_back"
    STOP = "stop"


@dataclass(frozen=True, slots=True)
class TokenAllowance:
    """One tier's allowance and use: the week's, and for standard also the day's."""

    tier: ModelTier
    weekly_limit: int | None
    used_this_week: int
    packs_left: int = 0
    daily_limit: int | None = None
    used_today: int = 0


def token_route(allowance: TokenAllowance) -> TokenRoute:
    """Where the next request's tokens come from, or whether it falls back or stops."""
    if allowance.tier is ModelTier.STANDARD:
        within_day = allowance.daily_limit is None or allowance.used_today < allowance.daily_limit
        within_week = (
            allowance.weekly_limit is None or allowance.used_this_week < allowance.weekly_limit
        )
        return TokenRoute.WITHIN_ALLOWANCE if within_day and within_week else TokenRoute.STOP
    if allowance.weekly_limit is None or allowance.used_this_week < allowance.weekly_limit:
        return TokenRoute.WITHIN_ALLOWANCE
    if allowance.packs_left > 0:
        return TokenRoute.FROM_PACKS
    return TokenRoute.FALL_BACK


class TokenLimit(StrEnum):
    """Which allowance a request ran into; the code the agent and the client read."""

    FRONTIER_WEEK = "frontier_weekly_tokens"
    STANDARD_DAY = "standard_daily_tokens"
    STANDARD_WEEK = "standard_weekly_tokens"


@dataclass(frozen=True, slots=True)
class TokenDecision:
    """The route of the next request and, when it falls back or stops, the limit why."""

    route: TokenRoute
    reason: TokenLimit | None = None


def token_decision(allowance: TokenAllowance) -> TokenDecision:
    """The route with its reason: a used-up frontier week falls back, a standard limit stops."""
    route = token_route(allowance)
    if route is TokenRoute.FALL_BACK:
        return TokenDecision(route, TokenLimit.FRONTIER_WEEK)
    if route is not TokenRoute.STOP:
        return TokenDecision(route)
    daily = allowance.daily_limit
    if daily is not None and allowance.used_today >= daily:
        return TokenDecision(route, TokenLimit.STANDARD_DAY)
    return TokenDecision(route, TokenLimit.STANDARD_WEEK)


def beyond_allowance(limit: int | None, before: int, tokens: int) -> int:
    """How many of a request's tokens fall past the weekly allowance: what packs pay for."""
    if limit is None:
        return 0
    return max(before + tokens - limit, 0) - max(before - limit, 0)
