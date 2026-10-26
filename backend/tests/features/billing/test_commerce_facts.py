"""The catalogue as the platform operator's Leo reads it (agent AG-D5): every plan with its
prices per currency and its subscribers, every promo code with its status on the business date."""

from datetime import date
from uuid import UUID

from shosai.features.billing.application.catalogue import Catalogue
from shosai.features.billing.application.commerce_facts import CommerceFactsReader
from shosai.features.billing.application.promo_codes import PromoCodes
from tests.doubles.business_calendar import MOSCOW
from tests.features.billing.catalogue_bench import (
    TODAY,
    CatalogueBench,
    created,
    plan_draft,
    promo_draft,
)
from tests.harness.database_access import DatabaseAccess


async def test_plans_and_promo_codes_come_with_prices_subscribers_and_status(
    catalogue: CatalogueBench, homes: DatabaseAccess
) -> None:
    plan_id = await created(catalogue, "/v1/admin/plans", plan_draft("pro"))
    await created(catalogue, "/v1/admin/promo-codes", promo_draft("OLD", valid_until="2026-01-01"))
    catalogue.subscribers.by_plan[UUID(plan_id)] = 7
    facts = CommerceFactsReader(
        Catalogue(homes.transactions, (catalogue.subscribers, catalogue.subscribers)),
        PromoCodes(homes.transactions, clock=lambda: TODAY, business=MOSCOW),
    )

    plans = {plan.slug: plan for plan in await facts.plans()}
    [code] = await facts.promo_codes()

    assert plans["pro"].month_prices == {"RUB": 149_000, "USD": 1_500, "EUR": 1_400}
    assert plans["pro"].year_prices["USD"] == 15_000
    assert (plans["pro"].subscribers, plans["pro"].on_sale, plans["pro"].archived) == (
        7,
        True,
        False,
    )
    assert (code.code, code.status, code.percent_off) == ("OLD", "expired", 20)
    assert code.valid_until == date(2026, 1, 1)
