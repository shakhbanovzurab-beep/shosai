"""Promo codes: their status and the discount they give (the admin's promo form; draft rules).

A code is percent or fixed per currency; it may be limited to plans, to a period, to the
first payment, to a number of uses in all and per person, and to dates (inclusive, UTC).
A fixed discount applies only in a currency it names. A price never goes below zero. A
use is counted on a successful payment only, by the payment's own transaction.
"""

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from typing import Final

from shosai.features.billing.domain.money import Currency, Money
from shosai.features.billing.domain.plans import BillingPeriod

CODE: Final = re.compile(r"[A-Z0-9_-]{3,32}")
FIXED_MIN_MINOR: Final = 100
PERCENT_MAX: Final = 100


class PromoStatus(StrEnum):
    """Where a code stands today."""

    ACTIVE = "active"
    SCHEDULED = "scheduled"
    EXPIRED = "expired"
    EXHAUSTED = "exhausted"
    DISABLED = "disabled"


class PromoRefusal(StrEnum):
    """Why a code does not apply to a purchase."""

    NOT_ACTIVE = "promo_not_active"
    NOT_FOR_PLAN = "promo_not_for_plan"
    NOT_FOR_PERIOD = "promo_not_for_period"
    NOT_FOR_CURRENCY = "promo_not_for_currency"
    FIRST_PAYMENT_ONLY = "promo_first_payment_only"
    USED_UP_BY_PERSON = "promo_used_up"


@dataclass(frozen=True, slots=True)
class PromoCode:
    """A code as the admin set it, and how often it was used."""

    code: str
    percent_off: int | None = None
    amounts_off: Mapping[Currency, int] = field(default_factory=dict)
    plan_slugs: frozenset[str] | None = None
    period: BillingPeriod | None = None
    max_redemptions: int | None = None
    per_user_limit: int | None = None
    redemptions: int = 0
    valid_from: date | None = None
    valid_until: date | None = None
    first_payment_only: bool = False
    active: bool = True

    def __post_init__(self) -> None:
        if not CODE.fullmatch(self.code):
            message = "код — A-Z, 0-9, _ и -, 3–32 символа"
            raise ValueError(message)
        percent = self.percent_off is not None
        if percent == bool(self.amounts_off):
            message = "скидка — либо процент, либо суммы в валютах"
            raise ValueError(message)
        if percent and not 1 <= (self.percent_off or 0) <= PERCENT_MAX:
            message = "процент скидки — от 1 до 100"
            raise ValueError(message)
        if any(amount < FIXED_MIN_MINOR for amount in self.amounts_off.values()):
            message = "фиксированная скидка — от 100 минорных единиц"
            raise ValueError(message)

    def status(self, today: date) -> PromoStatus:
        """The code's status on a UTC date."""
        if not self.active:
            return PromoStatus.DISABLED
        if self.valid_from is not None and today < self.valid_from:
            return PromoStatus.SCHEDULED
        if self.valid_until is not None and today > self.valid_until:
            return PromoStatus.EXPIRED
        if self.max_redemptions is not None and self.redemptions >= self.max_redemptions:
            return PromoStatus.EXHAUSTED
        return PromoStatus.ACTIVE


@dataclass(frozen=True, slots=True)
class Purchase:
    """What a code is applied to."""

    price: Money
    plan_slug: str
    period: BillingPeriod
    first_payment: bool
    used_by_person: int
    today: date


def discounted(code: PromoCode, purchase: Purchase) -> Money | PromoRefusal:
    """The price after the code, or why the code does not apply."""
    refusal = _refusal(code, purchase)
    if refusal is not None:
        return refusal
    price = purchase.price
    if code.percent_off is not None:
        off = math.floor(price.minor * code.percent_off / PERCENT_MAX)
        return Money(price.currency, price.minor - off)
    return price.minus(Money(price.currency, code.amounts_off[price.currency]))


def _refusal(code: PromoCode, purchase: Purchase) -> PromoRefusal | None:
    checks = (
        (code.status(purchase.today) is PromoStatus.ACTIVE, PromoRefusal.NOT_ACTIVE),
        (
            code.plan_slugs is None or purchase.plan_slug in code.plan_slugs,
            PromoRefusal.NOT_FOR_PLAN,
        ),
        (code.period is None or code.period is purchase.period, PromoRefusal.NOT_FOR_PERIOD),
        (
            code.percent_off is not None or purchase.price.currency in code.amounts_off,
            PromoRefusal.NOT_FOR_CURRENCY,
        ),
        (not code.first_payment_only or purchase.first_payment, PromoRefusal.FIRST_PAYMENT_ONLY),
        (
            code.per_user_limit is None or purchase.used_by_person < code.per_user_limit,
            PromoRefusal.USED_UP_BY_PERSON,
        ),
    )
    return next((refusal for holds, refusal in checks if not holds), None)
