"""Promo codes: their status and the discount they give (the admin's promo form; draft rules).

A code is percent or fixed per currency; it may be limited to plans, to a period, to the
first payment, to a number of uses in all and per person, and to dates (inclusive, UTC).
A fixed discount applies only in a currency it names. A price never goes below zero. A
use is counted on a successful payment only, by the payment's own transaction. A code
whose last plan was removed names no plan and stays switched off until it names one.
Every broken rule carries the API's error code.
"""

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from typing import Final
from uuid import UUID

from shosai.features.billing.domain.money import Currency, Money
from shosai.features.billing.domain.plans import BillingPeriod

CODE: Final = re.compile(r"[A-Z0-9_-]{3,32}")
FIXED_MIN_MINOR: Final = 100
PERCENT_MAX: Final = 100
PLANS_MAX: Final = 50


class PromoRule(StrEnum):
    """A rule of a promo code; the value is the API's error code."""

    CODE = "promo_code_invalid"
    DISCOUNT = "promo_discount_ambiguous"
    PERCENT = "promo_percent_invalid"
    AMOUNT = "promo_amount_too_small"
    LIMITS = "promo_limits_invalid"
    DATES = "promo_dates_invalid"
    PLANS = "promo_needs_plans"


RULE_MESSAGES: Final = {
    PromoRule.CODE: "код — A-Z, 0-9, _ и -, 3–32 символа",
    PromoRule.DISCOUNT: "скидка — либо процент, либо суммы в валютах",
    PromoRule.PERCENT: "процент скидки — от 1 до 100",
    PromoRule.AMOUNT: "фиксированная скидка — от 100 минорных единиц",
    PromoRule.LIMITS: "лимиты активаций — от 1, на человека не больше общего",
    PromoRule.DATES: "дата начала не позже даты окончания",
    PromoRule.PLANS: "включённый код по тарифам называет от 1 до 50 тарифов",
}


class PromoRuleError(ValueError):
    """A promo code breaks a rule."""

    def __init__(self, rule: PromoRule) -> None:
        super().__init__(RULE_MESSAGES[rule])
        self.rule = rule
        self.code = rule.value


class PromoStatus(StrEnum):
    """Where a code stands today, judged in the cabinet's order (`promoStatus`)."""

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
    # None — все тарифы, в том числе будущие.
    plan_ids: frozenset[UUID] | None = None
    period: BillingPeriod | None = None
    max_redemptions: int | None = None
    per_user_limit: int | None = None
    redemptions: int = 0
    valid_from: date | None = None
    valid_until: date | None = None
    first_payment_only: bool = False
    active: bool = True

    def __post_init__(self) -> None:
        problem = promo_problem(self)
        if problem is not None:
            raise PromoRuleError(problem)

    def status(self, today: date) -> PromoStatus:
        """The code's status on a UTC date."""
        if not self.active:
            return PromoStatus.DISABLED
        if self.valid_until is not None and today > self.valid_until:
            return PromoStatus.EXPIRED
        if self.max_redemptions is not None and self.redemptions >= self.max_redemptions:
            return PromoStatus.EXHAUSTED
        if self.valid_from is not None and today < self.valid_from:
            return PromoStatus.SCHEDULED
        return PromoStatus.ACTIVE


def promo_problem(code: PromoCode) -> PromoRule | None:
    """The first rule the code breaks, or None."""
    percent = code.percent_off
    plans = code.plan_ids
    rules = (
        (CODE.fullmatch(code.code) is not None, PromoRule.CODE),
        ((percent is not None) != bool(code.amounts_off), PromoRule.DISCOUNT),
        (percent is None or 1 <= percent <= PERCENT_MAX, PromoRule.PERCENT),
        (all(amount >= FIXED_MIN_MINOR for amount in code.amounts_off.values()), PromoRule.AMOUNT),
        (_limits_hold(code.max_redemptions, code.per_user_limit), PromoRule.LIMITS),
        (
            code.valid_from is None
            or code.valid_until is None
            or code.valid_from <= code.valid_until,
            PromoRule.DATES,
        ),
        (
            plans is None or (len(plans) <= PLANS_MAX and (bool(plans) or not code.active)),
            PromoRule.PLANS,
        ),
    )
    return next((rule for holds, rule in rules if not holds), None)


def _limits_hold(total: int | None, per_user: int | None) -> bool:
    if total is not None and per_user is not None:
        return 1 <= per_user <= total
    return all(limit is None or limit >= 1 for limit in (total, per_user))


@dataclass(frozen=True, slots=True)
class Purchase:
    """What a code is applied to."""

    price: Money
    plan_id: UUID
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
            code.plan_ids is None or purchase.plan_id in code.plan_ids,
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
