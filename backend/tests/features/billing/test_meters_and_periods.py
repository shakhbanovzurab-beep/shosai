"""Usage windows, token routes, promo codes and money periods (BL-D3, BL-D4, BL-D7, BL-D8)."""

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from shosai.features.billing.domain.meters import (
    MinutesLeft,
    TokenAllowance,
    TokenRoute,
    month_window,
    token_route,
    week_window,
)
from shosai.features.billing.domain.money import Currency, Money
from shosai.features.billing.domain.periods import (
    Period,
    prorated,
    renewal_period_key,
    unused_refund,
)
from shosai.features.billing.domain.plans import BillingPeriod, ModelTier
from shosai.features.billing.domain.promos import (
    PromoCode,
    PromoRefusal,
    PromoStatus,
    Purchase,
    discounted,
)

START = datetime(2026, 10, 1, tzinfo=UTC)
moments = st.integers(0, 2 * 365 * 24 * 60).map(lambda minutes: START + timedelta(minutes=minutes))


@given(now=moments)
def test_the_month_and_the_week_contain_now_and_start_where_the_cabinet_says(now: datetime) -> None:
    month_start, next_month = month_window(now)
    week_start, next_week = week_window(now)

    assert month_start <= now < next_month
    assert month_start.day == 1
    assert week_start <= now < next_week
    assert week_start.weekday() == 0
    assert next_week - week_start == timedelta(days=7)


def test_minutes_are_judged_on_raw_seconds_and_uploads_are_checked_before_processing() -> None:
    left = MinutesLeft(limit_minutes=120, used_seconds=119 * 60 + 30)

    assert not left.exhausted
    assert left.remaining_minutes == 0
    assert left.covers(30)
    assert not left.covers(31)
    assert MinutesLeft(120, 120 * 60).exhausted
    assert MinutesLeft(None, 10**9).covers(10**9)


@pytest.mark.parametrize(
    ("allowance", "route"),
    [
        (TokenAllowance(ModelTier.FRONTIER, 100, 99), TokenRoute.WITHIN_ALLOWANCE),
        (TokenAllowance(ModelTier.FRONTIER, 100, 100, packs_left=5), TokenRoute.FROM_PACKS),
        (TokenAllowance(ModelTier.FRONTIER, 100, 100), TokenRoute.FALL_BACK),
        (TokenAllowance(ModelTier.FRONTIER, 0, 0), TokenRoute.FALL_BACK),
        (
            TokenAllowance(ModelTier.STANDARD, None, 10**9, daily_limit=50, used_today=49),
            TokenRoute.WITHIN_ALLOWANCE,
        ),
        (
            TokenAllowance(ModelTier.STANDARD, None, 0, daily_limit=50, used_today=50),
            TokenRoute.STOP,
        ),
    ],
)
def test_frontier_falls_back_after_packs_and_standard_stops_at_its_daily_limit(
    allowance: TokenAllowance, route: TokenRoute
) -> None:
    assert token_route(allowance) is route


@given(first=st.tuples(st.uuids(), moments), second=st.tuples(st.uuids(), moments))
def test_a_renewal_key_is_unique_per_subscription_and_date(
    first: tuple[uuid.UUID, datetime], second: tuple[uuid.UUID, datetime]
) -> None:
    same = first[0] == second[0] and first[1].date() == second[1].date()

    assert (renewal_period_key(*first) == renewal_period_key(*second)) is same


@given(
    price=st.integers(0, 10**7),
    units=st.integers(0, 50),
    days=st.integers(1, 366),
    offset_hours=st.integers(-48, 24 * 400),
)
def test_proration_and_refunds_never_exceed_the_period_s_price(
    price: int, units: int, days: int, offset_hours: int
) -> None:
    period = Period(START, START + timedelta(days=days))
    now = START + timedelta(hours=offset_hours)
    seat = Money(Currency.RUB, price)

    assert prorated(seat, units, period, now).minor <= price * units
    assert unused_refund(seat, period, now).minor <= price
    if now >= period.end:
        assert unused_refund(seat, period, now).minor == 0


def test_a_promo_code_s_status_and_its_discount() -> None:
    today = date(2026, 10, 17)
    purchase = Purchase(
        Money(Currency.RUB, 149_000),
        "professional",
        BillingPeriod.MONTH,
        first_payment=True,
        used_by_person=0,
        today=today,
    )
    fixed = PromoCode(
        "AUTUMN", amounts_off={Currency.RUB: 50_000}, plan_slugs=frozenset({"professional"})
    )

    assert discounted(PromoCode("HALF", percent_off=50), purchase) == Money(Currency.RUB, 74_500)
    assert discounted(fixed, purchase) == Money(Currency.RUB, 99_000)
    usd = Purchase(
        Money(Currency.USD, 1_500),
        "professional",
        BillingPeriod.MONTH,
        first_payment=True,
        used_by_person=0,
        today=today,
    )
    assert discounted(fixed, usd) is PromoRefusal.NOT_FOR_CURRENCY
    assert (
        PromoCode("SOON", percent_off=10, valid_from=date(2026, 11, 1)).status(today)
        is PromoStatus.SCHEDULED
    )
    assert (
        PromoCode("OLD", percent_off=10, valid_until=date(2026, 10, 1)).status(today)
        is PromoStatus.EXPIRED
    )
    assert (
        PromoCode("GONE", percent_off=10, max_redemptions=3, redemptions=3).status(today)
        is PromoStatus.EXHAUSTED
    )
    once = PromoCode("ONCE", percent_off=10, per_user_limit=1)
    again = Purchase(
        purchase.price,
        "professional",
        BillingPeriod.MONTH,
        first_payment=True,
        used_by_person=1,
        today=today,
    )
    assert discounted(once, again) is PromoRefusal.USED_UP_BY_PERSON
