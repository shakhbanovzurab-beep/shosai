"""Money, prices and plans follow the cabinet's catalogue rules (BL-D2)."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from shosai.features.billing.domain.currency import currency_for_country
from shosai.features.billing.domain.money import (
    FREE,
    Currency,
    MixedCurrenciesError,
    Money,
    Prices,
)
from shosai.features.billing.domain.plans import (
    Audience,
    BillingPeriod,
    ModelTier,
    Plan,
    PlanLimits,
    SeatRange,
)

LIMITS = PlanLimits(120, 0, 0)


def test_amounts_of_two_currencies_never_mix() -> None:
    with pytest.raises(MixedCurrenciesError):
        Money(Currency.RUB, 100).plus(Money(Currency.USD, 1))
    assert Money(Currency.EUR, 100).minus(Money(Currency.EUR, 300)) == Money(Currency.EUR, 0)


@pytest.mark.parametrize(
    "amounts",
    [
        {Currency.RUB: 0, Currency.USD: 10, Currency.EUR: 10},
        {Currency.RUB: 10, Currency.USD: 10},
        {Currency.RUB: -1, Currency.USD: 0, Currency.EUR: 0},
    ],
)
def test_a_period_s_prices_are_all_zero_or_all_positive_in_every_currency(
    amounts: dict[Currency, int],
) -> None:
    with pytest.raises(ValueError, match="цена"):
        Prices(amounts)


def test_a_team_plan_names_its_seats_and_a_custom_plan_has_no_price() -> None:
    paid = Prices({currency: 100 for currency in Currency})

    with pytest.raises(ValueError, match="места"):
        Plan("team", "Team", Audience.TEAM, LIMITS)
    with pytest.raises(ValueError, match="по запросу"):
        Plan("enterprise", "Enterprise", Audience.ENTERPRISE, LIMITS, custom_pricing=True,
             prices={BillingPeriod.MONTH: paid, BillingPeriod.YEAR: FREE})  # fmt: skip
    with pytest.raises(ValueError, match="slug"):
        Plan("Pro Plan", "Pro", Audience.INDIVIDUAL, LIMITS)
    team = Plan("team", "Team", Audience.TEAM, LIMITS, seats=SeatRange(2, 100))
    assert team.billed_per_seat()
    assert team.free


@given(seats=st.integers(-5, 200))
def test_a_seat_range_admits_only_its_seats(seats: int) -> None:
    assert SeatRange(2, 100).allows(seats) is (2 <= seats <= 100)


def test_unlimited_covers_every_limit_and_zero_covers_only_zero() -> None:
    unlimited = PlanLimits(None, None, None, {ModelTier.STANDARD: None, ModelTier.FRONTIER: None})

    assert unlimited.covers(LIMITS)
    assert not LIMITS.covers(unlimited)


@pytest.mark.parametrize(
    ("country", "currency"),
    [
        ("RU", Currency.RUB),
        ("de", Currency.EUR),
        ("NO", Currency.EUR),
        ("US", Currency.USD),
        (None, Currency.USD),
    ],
)
def test_the_currency_follows_the_country(country: str | None, currency: Currency) -> None:
    assert currency_for_country(country) is currency
