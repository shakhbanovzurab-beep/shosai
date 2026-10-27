"""Rows of the catalogue to the domain and back: plans and promo codes.

A row is read into the domain's `Plan` or `PromoCode`, which checks its rules; a write
copies the domain's fields onto the row, so a rule the domain refuses never reaches SQL.
"""

from collections.abc import Mapping
from datetime import datetime

from sqlalchemy.exc import IntegrityError

from shosai.features.billing.domain.money import Currency, Prices
from shosai.features.billing.domain.plans import (
    Audience,
    BillingPeriod,
    Capability,
    ModelTier,
    Plan,
    PlanLimits,
    SeatRange,
)
from shosai.features.billing.domain.promos import PromoCode
from shosai.features.billing.infrastructure.plan_records import TariffRecord
from shosai.features.billing.infrastructure.promo_records import PromoCodeRecord

UNIQUE_VIOLATION = "23505"
BOTH_PERIODS = "both"


def violates_unique(error: IntegrityError, index: str) -> bool:
    """Whether the failed statement broke the named unique index."""
    origin = error.orig
    diag = getattr(origin, "diag", None)
    return (
        getattr(origin, "sqlstate", None) == UNIQUE_VIOLATION
        and getattr(diag, "constraint_name", None) == index
    )


def prices_of(row: TariffRecord, period: BillingPeriod) -> Prices:
    """A period's prices of a row."""
    return Prices({currency: getattr(row, price_column(period, currency)) for currency in Currency})


def price_column(period: BillingPeriod, currency: Currency) -> str:
    """The column of one price: `price_month_rub`."""
    return f"price_{period.value}_{currency.value.lower()}"


def plan_of(row: TariffRecord) -> Plan:
    """The domain plan of a row."""
    seats = None if row.seats_min is None else SeatRange(row.seats_min, row.seats_max)
    limits = PlanLimits(
        meeting_minutes_per_month=row.meeting_minutes_per_month,
        file_manager_gb=row.file_manager_gb,
        knowledge_base_mb=row.knowledge_base_mb,
        weekly_tokens={
            ModelTier.STANDARD: row.weekly_standard_tokens,
            ModelTier.FRONTIER: row.weekly_frontier_tokens,
        },
        daily_standard_tokens=row.daily_standard_tokens,
        room_participants=row.room_participants,
    )
    return Plan(
        slug=row.slug, name=row.name, audience=Audience(row.audience), limits=limits,
        capabilities=frozenset(Capability(item) for item in row.capabilities),
        prices={period: prices_of(row, period) for period in BillingPeriod},
        seats=seats, custom_pricing=row.custom_pricing, description=row.description,
        features=tuple(row.features), sort_order=row.sort_order, on_sale=row.is_active,
        featured=row.is_featured, archived=row.archived_at is not None,
    )  # fmt: skip


def write_plan(row: TariffRecord, plan: Plan, now: datetime) -> None:
    """Copy a plan onto its row; archiving stamps the moment, restoring clears it."""
    row.slug, row.name, row.description = plan.slug, plan.name, plan.description
    row.audience, row.custom_pricing = plan.audience.value, plan.custom_pricing
    row.seats_min = None if plan.seats is None else plan.seats.min
    row.seats_max = None if plan.seats is None else plan.seats.max
    for period, prices in plan.prices.items():
        for currency, amount in prices.amounts.items():
            setattr(row, price_column(period, currency), amount)
    limits = plan.limits
    row.meeting_minutes_per_month = limits.meeting_minutes_per_month
    row.file_manager_gb, row.knowledge_base_mb = limits.file_manager_gb, limits.knowledge_base_mb
    row.weekly_standard_tokens = limits.weekly_tokens[ModelTier.STANDARD]
    row.weekly_frontier_tokens = limits.weekly_tokens[ModelTier.FRONTIER]
    row.daily_standard_tokens = limits.daily_standard_tokens
    row.room_participants = limits.room_participants
    row.capabilities = sorted(item.value for item in plan.capabilities)
    row.features = list(plan.features)
    row.is_active, row.is_featured, row.sort_order = plan.on_sale, plan.featured, plan.sort_order
    if not plan.archived:
        row.archived_at = None
    elif row.archived_at is None:
        row.archived_at = now
    row.updated_at = now


def amounts_of(row: PromoCodeRecord) -> Mapping[Currency, int]:
    """The fixed discount of a row per currency it names."""
    amounts = {
        Currency.RUB: row.amount_off_rub,
        Currency.USD: row.amount_off_usd,
        Currency.EUR: row.amount_off_eur,
    }
    return {currency: amount for currency, amount in amounts.items() if amount is not None}


def promo_of(row: PromoCodeRecord) -> PromoCode:
    """The domain promo code of a row."""
    plans = None if row.plan_ids is None else frozenset(row.plan_ids)
    period = None if row.billing_period == BOTH_PERIODS else BillingPeriod(row.billing_period)
    return PromoCode(
        code=row.code, percent_off=row.percent_off, amounts_off=amounts_of(row), plan_ids=plans,
        period=period, max_redemptions=row.max_redemptions, per_user_limit=row.per_user_limit,
        redemptions=row.redemptions, valid_from=row.valid_from, valid_until=row.valid_until,
        first_payment_only=row.first_payment_only, active=row.is_active,
    )  # fmt: skip


def write_promo(row: PromoCodeRecord, promo: PromoCode) -> None:
    """Copy a promo code's settings onto its row; its use count is never written here."""
    row.code, row.percent_off = promo.code, promo.percent_off
    row.amount_off_rub = promo.amounts_off.get(Currency.RUB)
    row.amount_off_usd = promo.amounts_off.get(Currency.USD)
    row.amount_off_eur = promo.amounts_off.get(Currency.EUR)
    row.plan_ids = None if promo.plan_ids is None else sorted(promo.plan_ids)
    row.billing_period = BOTH_PERIODS if promo.period is None else promo.period.value
    row.max_redemptions, row.per_user_limit = promo.max_redemptions, promo.per_user_limit
    row.valid_from, row.valid_until = promo.valid_from, promo.valid_until
    row.first_payment_only, row.is_active = promo.first_payment_only, promo.active
