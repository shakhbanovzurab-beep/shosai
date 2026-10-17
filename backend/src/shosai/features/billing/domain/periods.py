"""Periods of money: the renewal key, prorated additions and refunds of the unused part.

The renewal key — the subscription and the date of the expiry it renews — makes one
charge per period (inv-4); it keeps the draft's form, so migrated attempts stay unique.
An added seat pays the rest of the period at once (BL-D7); a refund returns the unused
rest of the period only (BL-D8). Both round down, so neither exceeds the period's price.
"""

import math
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from shosai.features.billing.domain.money import Money


def renewal_period_key(subscription_id: UUID, expires_at: datetime) -> str:
    """`<subscription id>:<YYYY-MM-DD>` of the expiry the renewal extends."""
    return f"{subscription_id}:{expires_at.date().isoformat()}"


@dataclass(frozen=True, slots=True)
class Period:
    """A paid period: its start and its end."""

    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.end <= self.start:
            message = "период кончается позже, чем начинается"
            raise ValueError(message)

    def unused_share(self, now: datetime) -> float:
        """The share of the period still ahead of `now`, from 0 to 1."""
        if now <= self.start:
            return 1.0
        if now >= self.end:
            return 0.0
        return (self.end - now) / (self.end - self.start)


def prorated(price: Money, units: int, period: Period, now: datetime) -> Money:
    """What `units` more seats cost for the rest of the period."""
    if units < 0:
        message = "добавляется неотрицательное число мест"
        raise ValueError(message)
    return Money(price.currency, math.floor(price.minor * units * period.unused_share(now)))


def unused_refund(paid: Money, period: Period, now: datetime) -> Money:
    """The part of a payment for the period still ahead; used time is never returned."""
    return Money(paid.currency, math.floor(paid.minor * period.unused_share(now)))
