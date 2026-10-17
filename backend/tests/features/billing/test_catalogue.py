"""The admin's plan catalogue in the cabinet's contract (billing step 2)."""

from uuid import UUID, uuid4

import httpx

from shosai.core.kernel.homes import Home
from shosai.features.billing.application.catalogue import CATALOGUE_SCOPE
from shosai.features.billing.domain.plans import FREE_PLAN_ID
from tests.features.billing.catalogue_bench import (
    CatalogueBench,
    created,
    plan_draft,
    promo_draft,
)
from tests.harness.connections import fetch_value
from tests.harness.run_slot import RunSlot

PLANS = "/v1/admin/plans"
PROMOS = "/v1/admin/promo-codes"
# Поля тарифа из contract.ts кабинета.
CABINET_PLAN = {
    "id", "name", "slug", "description", "audience", "seats", "custom_pricing", "price_monthly",
    "price_yearly", "limits", "capabilities", "features", "is_active", "is_featured",
    "sort_order", "subscribers", "archived", "created_at", "updated_at",
}  # fmt: skip
CABINET_LIMITS = {"meeting_minutes_per_month", "file_manager_gb", "knowledge_base_mb"}
CABINET_CAPABILITIES = {
    "shared_workspace", "member_management", "centralized_billing", "sso", "admin_controls",
    "priority_support", "usage_analytics",
}  # fmt: skip


def code_of(answer: httpx.Response) -> str:
    return str(answer.json()["error"]["code"])


async def test_the_list_starts_with_the_seeded_free_plan_in_the_cabinet_s_shape(
    catalogue: CatalogueBench,
) -> None:
    listed = await catalogue.admin.get(PLANS)
    refused = await catalogue.anonymous.get(PLANS)

    [free] = listed.json()["plans"]
    assert set(free) == CABINET_PLAN
    assert set(free["limits"]) >= CABINET_LIMITS
    assert set(free["capabilities"]) == {*CABINET_CAPABILITIES, "frontier_models"}
    assert (free["id"], free["slug"], free["subscribers"], free["archived"]) == (
        str(FREE_PLAN_ID), "free", 0, False,
    )  # fmt: skip
    assert free["price_monthly"] == {"RUB": 0, "USD": 0, "EUR": 0}
    assert free["limits"]["meeting_minutes_per_month"] == 120
    tokens = ("weekly_standard_tokens", "weekly_frontier_tokens", "daily_standard_tokens")
    assert [free["limits"][name] for name in tokens] == [1_000_000, 0, 250_000]
    assert (refused.status_code, code_of(refused)) == (401, "admin_sign_in_required")


async def test_a_plan_is_created_and_patched_key_by_key_on_a_free_slug(
    catalogue: CatalogueBench,
) -> None:
    frontier = {**plan_draft("pro")["capabilities"], "frontier_models": True}
    plan_id = await created(catalogue, PLANS, plan_draft("pro", capabilities=frontier))
    taken = await catalogue.admin.post(PLANS, json=plan_draft("pro"))
    patched = await catalogue.admin.patch(
        f"{PLANS}/{plan_id}",
        json={
            "name": "  Pro  ",
            "limits": {"file_manager_gb": 250},
            "capabilities": {**plan_draft("pro")["capabilities"], "sso": True},
        },
    )

    assert (taken.status_code, code_of(taken)) == (409, "plan_slug_taken")
    plan = patched.json()
    assert set(plan) == CABINET_PLAN
    assert plan["name"] == "Pro"
    assert plan["limits"]["file_manager_gb"] == 250
    assert plan["limits"]["knowledge_base_mb"] == 100
    assert plan["capabilities"]["sso"] is True
    assert plan["capabilities"]["frontier_models"] is True


async def test_catalogue_rules_answer_422_with_their_codes(catalogue: CatalogueBench) -> None:
    drafts = {
        "plan_team_needs_seats": plan_draft("team", audience="team"),
        "plan_custom_has_price": plan_draft("corp", custom_pricing=True),
        "plan_prices_mixed": plan_draft("odd", price_yearly={"RUB": 0, "USD": 10, "EUR": 10}),
        "plan_seats_invalid": plan_draft("many", seats={"min": 10, "max": 5}),
        "validation_error": plan_draft("Bad Slug"),
    }

    answers = {
        code: await catalogue.admin.post(PLANS, json=draft) for code, draft in drafts.items()
    }

    assert {code: (a.status_code, code_of(a)) for code, a in answers.items()} == {
        code: (422, code) for code in drafts
    }


async def test_a_plan_with_subscribers_is_archived_and_one_without_leaves_promo_scopes(
    catalogue: CatalogueBench,
) -> None:
    kept = await created(catalogue, PLANS, plan_draft("start"))
    held = await created(catalogue, PLANS, plan_draft("max", is_featured=True))
    both = await created(
        catalogue, PROMOS, promo_draft("BOTH", scope="plans", plan_ids=[kept, held])
    )
    only = await created(catalogue, PROMOS, promo_draft("ONLY", scope="plans", plan_ids=[kept]))
    catalogue.subscribers.by_plan[UUID(held)] = 3

    archived = (await catalogue.admin.delete(f"{PLANS}/{held}")).json()
    again = await catalogue.admin.delete(f"{PLANS}/{held}")
    edited = await catalogue.admin.patch(f"{PLANS}/{held}", json={"name": "Max+"})
    restored = (await catalogue.admin.patch(f"{PLANS}/{held}", json={"archived": False})).json()
    deleted = (await catalogue.admin.delete(f"{PLANS}/{kept}")).json()
    promos = {p["id"]: p for p in (await catalogue.admin.get(PROMOS)).json()["promo_codes"]}

    assert archived["result"] == "archived"
    assert archived["promo_codes_updated"] == 0
    plan = archived["plan"]
    assert (plan["archived"], plan["is_active"], plan["is_featured"], plan["subscribers"]) == (
        True, False, False, 3,
    )  # fmt: skip
    assert (again.status_code, code_of(again)) == (409, "plan_archived_with_subscribers")
    assert (edited.status_code, code_of(edited)) == (409, "plan_archived")
    assert (restored["archived"], restored["is_active"]) == (False, False)
    assert deleted == {"result": "deleted", "plan": None, "promo_codes_updated": 2}
    assert (promos[both]["plan_ids"], promos[both]["is_active"]) == ([held], True)
    assert (promos[only]["plan_ids"], promos[only]["is_active"]) == ([], False)
    assert promos[only]["status"] == "disabled"


async def test_the_free_plan_is_never_removed_archived_or_priced(catalogue: CatalogueBench) -> None:
    free = f"{PLANS}/{FREE_PLAN_ID}"
    priced = {"price_monthly": {"RUB": 100, "USD": 100, "EUR": 100}}

    refusals = [
        await catalogue.admin.delete(free),
        await catalogue.admin.patch(free, json={"archived": True}),
        await catalogue.admin.patch(free, json=priced),
        await catalogue.admin.patch(free, json={"slug": "basic"}),
    ]
    renamed = await catalogue.admin.patch(free, json={"name": "Free forever"})
    missing = await catalogue.admin.delete(f"{PLANS}/{uuid4()}")

    assert {(a.status_code, code_of(a)) for a in refusals} == {(409, "free_plan_locked")}
    assert renamed.json()["name"] == "Free forever"
    assert (missing.status_code, code_of(missing)) == (404, "plan_not_found")


async def test_the_catalogue_exists_only_in_the_eu_home(run_slot: RunSlot) -> None:
    connections = run_slot.claimed.connections
    tables = ("tariffs", "promo_codes", "payment_routes")

    async def present(home: Home) -> list[object]:
        return [
            await fetch_value(connections[home], "SELECT to_regclass(%s)", (t,)) for t in tables
        ]

    eu = await present(Home.EU)
    ru = await present(Home.RU)
    routes = await fetch_value(
        connections[Home.EU],
        "SELECT string_agg(scope || ':' || method || ':' || enabled, ',' ORDER BY scope, position)"
        " FROM payment_routes",
    )

    assert CATALOGUE_SCOPE.home is Home.EU
    assert all(name is not None for name in eu)
    assert ru == [None, None, None]
    assert routes == "FX:lava:true,FX:lava_paypal:true,RUB:tbank:true,RUB:cloudpayments:false"
