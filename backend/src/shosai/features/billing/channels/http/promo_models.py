"""The admin's promo code in the cabinet's contract (`admin-plans/domain/contract.ts`), and back.

A draft is normalised as the cabinet does: a percent code carries no amounts, a fixed
one no percent, scope "all" no plan ids. A PATCH merges into the current code and the
result is checked whole.
"""

from datetime import date, datetime
from http import HTTPStatus
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, Field, StringConstraints

from shosai.core.kernel.errors import AppError
from shosai.features.billing.channels.http.plan_models import Strict, validated
from shosai.features.billing.domain.money import MAX_MINOR, Currency
from shosai.features.billing.domain.plans import BillingPeriod
from shosai.features.billing.domain.promos import (
    FIXED_MIN_MINOR,
    PLANS_MAX,
    PromoCode,
    PromoRuleError,
    PromoStatus,
)

type DiscountType = Literal["percent", "fixed"]
type PromoScope = Literal["all", "plans"]
type PeriodScope = Literal["month", "year", "both"]
AmountOff = Annotated[int, Field(ge=FIXED_MIN_MINOR, le=MAX_MINOR)]


def upper_case(value: object) -> object:
    """A code as the cabinet stores it: trimmed and upper-case."""
    return value.strip().upper() if isinstance(value, str) else value


Code = Annotated[
    str,
    BeforeValidator(upper_case),
    StringConstraints(min_length=3, max_length=32, pattern=r"^[A-Z0-9_-]+$"),
]


class PromoDraftBody(Strict):
    """A promo code as the admin's form sends it."""

    code: Code
    discount_type: DiscountType
    percent_off: Annotated[int, Field(ge=1, le=100)] | None
    amounts_off: dict[Currency, AmountOff]
    scope: PromoScope
    plan_ids: Annotated[list[UUID], Field(max_length=PLANS_MAX)]
    billing_period: PeriodScope
    max_redemptions: Annotated[int, Field(ge=1, le=10_000_000)] | None
    per_user_limit: Annotated[int, Field(ge=1, le=1000)] | None
    valid_from: date | None
    valid_until: date | None
    first_payment_only: bool
    is_active: bool


class PromoPatchBody(Strict):
    """Any part of the draft."""

    code: str | None = None
    discount_type: DiscountType | None = None
    percent_off: int | None = None
    amounts_off: dict[Currency, int] | None = None
    scope: PromoScope | None = None
    plan_ids: list[UUID] | None = None
    billing_period: PeriodScope | None = None
    max_redemptions: int | None = None
    per_user_limit: int | None = None
    valid_from: date | None = None
    valid_until: date | None = None
    first_payment_only: bool | None = None
    is_active: bool | None = None


class PromoView(BaseModel):
    """A promo code as the admin's list shows it; the status is judged today in UTC."""

    id: UUID
    code: str
    discount_type: DiscountType
    percent_off: int | None
    amounts_off: dict[Currency, int]
    scope: PromoScope
    plan_ids: list[UUID]
    billing_period: PeriodScope
    max_redemptions: int | None
    per_user_limit: int | None
    redemptions: int
    valid_from: date | None
    valid_until: date | None
    first_payment_only: bool
    is_active: bool
    status: PromoStatus
    created_at: datetime


def draft_of(promo: PromoCode) -> PromoDraftBody:
    """The contract's draft of a domain promo code."""
    percent = promo.percent_off is not None
    return PromoDraftBody(
        code=promo.code, discount_type="percent" if percent else "fixed",
        percent_off=promo.percent_off, amounts_off=dict(promo.amounts_off),
        scope="all" if promo.plan_ids is None else "plans",
        plan_ids=sorted(promo.plan_ids or ()),
        billing_period="both" if promo.period is None else promo.period.value,
        max_redemptions=promo.max_redemptions, per_user_limit=promo.per_user_limit,
        valid_from=promo.valid_from, valid_until=promo.valid_until,
        first_payment_only=promo.first_payment_only, is_active=promo.active,
    )  # fmt: skip


def view_of(promo_id: UUID, promo: PromoCode, created_at: datetime, today: date) -> PromoView:
    """The contract's promo code."""
    return PromoView(
        **draft_of(promo).model_dump(), id=promo_id, redemptions=promo.redemptions,
        status=promo.status(today), created_at=created_at,
    )  # fmt: skip


def promo_of(body: PromoDraftBody) -> PromoCode:
    """The domain code of a normalised draft; a broken rule is a 422 with its code."""
    percent = body.discount_type == "percent"
    if body.scope == "plans" and not body.plan_ids:
        raise AppError("promo_needs_plans", HTTPStatus.UNPROCESSABLE_CONTENT)
    try:
        return PromoCode(
            code=body.code, percent_off=body.percent_off if percent else None,
            amounts_off={} if percent else body.amounts_off,
            plan_ids=None if body.scope == "all" else frozenset(body.plan_ids),
            period=None if body.billing_period == "both" else BillingPeriod(body.billing_period),
            max_redemptions=body.max_redemptions, per_user_limit=body.per_user_limit,
            valid_from=body.valid_from, valid_until=body.valid_until,
            first_payment_only=body.first_payment_only, active=body.is_active,
        )  # fmt: skip
    except PromoRuleError as error:
        raise AppError(error.code, HTTPStatus.UNPROCESSABLE_CONTENT) from error


def merged_draft(current: PromoDraftBody, patch: PromoPatchBody) -> PromoDraftBody:
    """The current draft with the patch's fields over it, checked whole."""
    merged: dict[str, Any] = {**current.model_dump(), **patch.model_dump(exclude_unset=True)}
    return validated(PromoDraftBody, merged)
