"""The usage windows and allowances: minutes a month, tokens a week (BL-D3, BL-D4).

Minutes reset on the first day of a month in UTC, tokens on Monday 00:00 UTC. Minutes are
counted in seconds and judged on the raw total, never on a rounded remainder. A frontier
request past its weekly allowance spends packs, then falls back to a standard model; a
standard request past the plan's daily tokens stops with its reason (BL-D4).
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from shosai.features.billing.domain.plans import ModelTier

SECONDS_IN_MINUTE = 60
DECEMBER = 12


def month_window(now: datetime) -> tuple[datetime, datetime]:
    """The UTC month containing `now`: its first moment and the next month's."""
    start = now.astimezone(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == DECEMBER:
        return start, start.replace(year=start.year + 1, month=1)
    return start, start.replace(month=start.month + 1)


def tombstones_since(now: datetime) -> datetime:
    """The earliest meeting start whose tombstone still matters: the previous month's start.

    A meeting deleted late may still fall into last month; older months count no more.
    """
    start, _ = month_window(now)
    previous, _ = month_window(start - timedelta(microseconds=1))
    return previous


def week_window(now: datetime) -> tuple[datetime, datetime]:
    """The UTC week containing `now`, from Monday 00:00 to the next Monday."""
    day = now.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    start = day - timedelta(days=day.weekday())
    return start, start + timedelta(days=7)


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
