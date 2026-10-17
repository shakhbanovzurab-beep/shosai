"""Entitlements are judged by time: a lapsed plan is the Free plan (billing plan §1.2; ADR 0054)."""

from datetime import UTC, datetime, timedelta

from hypothesis import given
from hypothesis import strategies as st

from shosai.features.billing.domain.entitlements import (
    RENEWAL_GRACE,
    QueuedPlan,
    SubscriptionFacts,
    access_deadline,
    days_left,
    entitled,
    next_change,
)
from shosai.features.billing.domain.money import Currency, Prices
from shosai.features.billing.domain.plans import Audience, BillingPeriod, Plan, PlanLimits

START = datetime(2026, 10, 1, tzinfo=UTC)
FREE = Plan("basic", "Basic", Audience.INDIVIDUAL, PlanLimits(120, 0, 0))
PAID_PRICES = Prices({Currency.RUB: 149_000, Currency.USD: 1_500, Currency.EUR: 1_400})
PRO = Plan(
    "professional",
    "Professional",
    Audience.INDIVIDUAL,
    PlanLimits(None, 100, 100),
    prices={BillingPeriod.MONTH: PAID_PRICES, BillingPeriod.YEAR: PAID_PRICES},
)
moments = st.integers(-60 * 24 * 60, 60 * 24 * 60).map(
    lambda minutes: START + timedelta(minutes=minutes)
)
facts = st.builds(
    SubscriptionFacts,
    plan=st.just(PRO),
    expires_at=st.none() | moments,
    auto_renew=st.booleans(),
    trial=st.booleans(),
)


@given(facts=facts, now=moments)
def test_a_lapsed_plan_never_grants_more_than_free(facts: SubscriptionFacts, now: datetime) -> None:
    deadline = access_deadline(facts)
    result = entitled(facts, FREE, now)

    if deadline is not None and now >= deadline:
        assert result.plan == FREE
        assert FREE.limits.covers(result.plan.limits)
        assert not result.paid


@given(facts=facts, now=moments)
def test_grace_comes_only_with_auto_renewal_and_never_for_a_trial(
    facts: SubscriptionFacts, now: datetime
) -> None:
    result = entitled(facts, FREE, now)

    if result.in_grace:
        assert facts.auto_renew
        assert not facts.trial
        assert facts.expires_at is not None
        assert facts.expires_at <= now < facts.expires_at + RENEWAL_GRACE


def test_the_grace_is_seven_days_after_a_failed_renewal() -> None:
    renewing = SubscriptionFacts(PRO, START, auto_renew=True)

    assert entitled(renewing, FREE, START + timedelta(days=6)).plan == PRO
    assert entitled(renewing, FREE, START + timedelta(days=7)).plan == FREE
    assert entitled(SubscriptionFacts(PRO, START, auto_renew=False), FREE, START).plan == FREE


def test_no_subscription_or_no_end_is_judged_plainly() -> None:
    assert entitled(None, FREE, START).plan == FREE
    assert entitled(SubscriptionFacts(PRO, None, auto_renew=False), FREE, START).paid


@given(now=moments)
def test_days_left_round_up_and_never_go_negative(now: datetime) -> None:
    left = days_left(START, now)

    assert left is not None
    assert left >= 0
    if now < START:
        assert left * timedelta(days=1) >= START - now


MAX = Plan(
    "max",
    "Max",
    Audience.INDIVIDUAL,
    PlanLimits(None, 250, 1024),
    prices={BillingPeriod.MONTH: PAID_PRICES, BillingPeriod.YEAR: PAID_PRICES},
)


def test_queued_plans_run_one_after_another_from_the_expiry_without_grace() -> None:
    held = SubscriptionFacts(
        MAX, START, auto_renew=True, queued=(QueuedPlan(PRO, 10), QueuedPlan(MAX, 5))
    )

    def plan_at(days: float) -> str:
        return entitled(held, FREE, START + timedelta(days=days)).plan.slug

    assert [plan_at(d) for d in (-1, 0, 9.9, 10, 14.9, 15)] == [
        "max", "professional", "professional", "max", "max", "basic",
    ]  # fmt: skip
    assert access_deadline(held) == START
    assert entitled(held, FREE, START + timedelta(days=3)).paid_until == START + timedelta(days=10)


@given(facts=facts, now=moments)
def test_the_plan_in_force_holds_until_the_next_change(
    facts: SubscriptionFacts, now: datetime
) -> None:
    change = next_change(facts, now)
    before = entitled(facts, FREE, now)

    if change is None:
        assert entitled(facts, FREE, now + timedelta(days=400)).plan == before.plan
    else:
        assert change > now
        assert entitled(facts, FREE, change - timedelta(microseconds=1)).plan == before.plan
