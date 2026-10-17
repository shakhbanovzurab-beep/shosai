"""The admin's promo codes in the cabinet's contract (billing step 2)."""

from uuid import UUID

import httpx

from shosai.core.kernel.homes import Home
from tests.features.billing.catalogue_bench import (
    CatalogueBench,
    created,
    plan_draft,
    promo_draft,
)
from tests.harness.run_slot import RunSlot

PLANS = "/v1/admin/plans"
PROMOS = "/v1/admin/promo-codes"
# Поля промокода из contract.ts кабинета.
CABINET_PROMO = {
    "id", "code", "discount_type", "percent_off", "amounts_off", "scope", "plan_ids",
    "billing_period", "max_redemptions", "per_user_limit", "redemptions", "valid_from",
    "valid_until", "first_payment_only", "is_active", "status", "created_at",
}  # fmt: skip


def code_of(answer: httpx.Response) -> str:
    return str(answer.json()["error"]["code"])


async def used(run_slot: RunSlot, promo_id: str, times: int) -> None:
    """Payments counted `times` uses of the code."""
    await run_slot.claimed.connections[Home.EU].execute(
        "UPDATE promo_codes SET redemptions = %s WHERE id = %s", (times, promo_id)
    )


async def test_a_code_is_stored_upper_case_once_and_its_status_follows_the_cabinet(
    catalogue: CatalogueBench, run_slot: RunSlot
) -> None:
    drafts = {
        "active": promo_draft(" spring "),
        "scheduled": promo_draft("LATER", valid_from="2026-11-01"),
        "expired": promo_draft("OLD", valid_until="2026-10-01"),
        "exhausted": promo_draft("GONE", max_redemptions=2, valid_from="2026-11-01"),
        "disabled": promo_draft("OFF", is_active=False, valid_until="2026-10-01"),
    }
    ids = {status: await created(catalogue, PROMOS, draft) for status, draft in drafts.items()}
    await used(run_slot, ids["exhausted"], 2)
    taken = await catalogue.admin.post(PROMOS, json=promo_draft("Spring"))

    listed = (await catalogue.admin.get(PROMOS)).json()["promo_codes"]

    by_id = {item["id"]: item for item in listed}
    assert all(set(item) == CABINET_PROMO for item in listed)
    assert {status: by_id[ids[status]]["status"] for status in drafts} == {s: s for s in drafts}
    assert by_id[ids["active"]]["code"] == "SPRING"
    assert listed[0]["code"] == "OFF"
    assert (taken.status_code, code_of(taken)) == (409, "promo_code_taken")


async def test_a_code_names_only_existing_unarchived_plans(catalogue: CatalogueBench) -> None:
    plan = await created(catalogue, PLANS, plan_draft("pro"))
    scoped = await created(catalogue, PROMOS, promo_draft("PRO", scope="plans", plan_ids=[plan]))
    catalogue.subscribers.by_plan[UUID(plan)] = 1
    await catalogue.admin.delete(f"{PLANS}/{plan}")
    refusals = {
        "promo_plan_archived": promo_draft("NEW", scope="plans", plan_ids=[plan]),
        "promo_plan_unknown": promo_draft(
            "LOST", scope="plans", plan_ids=["0199f2a0-0000-7000-8000-00000000dead"]
        ),
        "promo_needs_plans": promo_draft("NONE", scope="plans", plan_ids=[]),
    }

    answers = {code: await catalogue.admin.post(PROMOS, json=d) for code, d in refusals.items()}
    kept = await catalogue.admin.patch(f"{PROMOS}/{scoped}", json={"percent_off": 30})

    assert {code: (a.status_code, code_of(a)) for code, a in answers.items()} == {
        code: (422, code) for code in refusals
    }
    assert (kept.status_code, kept.json()["plan_ids"]) == (200, [plan])


async def test_a_patch_switches_the_discount_kind_and_keeps_the_use_count(
    catalogue: CatalogueBench, run_slot: RunSlot
) -> None:
    promo = await created(catalogue, PROMOS, promo_draft("AUTUMN", max_redemptions=10))
    await used(run_slot, promo, 4)

    fixed = await catalogue.admin.patch(
        f"{PROMOS}/{promo}",
        json={"discount_type": "fixed", "amounts_off": {"RUB": 50_000}, "redemptions": 0},
    )
    switched = await catalogue.admin.patch(
        f"{PROMOS}/{promo}", json={"discount_type": "fixed", "amounts_off": {"RUB": 50_000}}
    )
    below = await catalogue.admin.patch(f"{PROMOS}/{promo}", json={"max_redemptions": 3})
    too_small = await catalogue.admin.patch(f"{PROMOS}/{promo}", json={"amounts_off": {"USD": 99}})
    removed = await catalogue.admin.delete(f"{PROMOS}/{promo}")
    again = await catalogue.admin.delete(f"{PROMOS}/{promo}")

    assert (fixed.status_code, code_of(fixed)) == (422, "validation_error")
    body = switched.json()
    assert (body["discount_type"], body["percent_off"], body["amounts_off"]) == (
        "fixed", None, {"RUB": 50_000},
    )  # fmt: skip
    assert body["redemptions"] == 4
    assert (below.status_code, code_of(below)) == (422, "promo_limit_below_used")
    assert below.json()["error"]["params"] == {"redemptions": 4}
    assert (too_small.status_code, code_of(too_small)) == (422, "validation_error")
    assert (removed.status_code, again.status_code, code_of(again)) == (
        204, 404, "promo_not_found",
    )  # fmt: skip
