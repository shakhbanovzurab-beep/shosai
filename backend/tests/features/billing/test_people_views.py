"""The person's plans, usage and sales inquiries in the cabinet's contract (step 6)."""

from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select

from shosai.core.events.records import OutboxMessage
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.billing.domain.meters import month_window, week_window
from shosai.features.billing.infrastructure.sales_records import SalesInquiryRecord
from tests.features.billing.catalogue_bench import created, plan_draft
from tests.features.billing.people_bench import PeopleBench, bearer
from tests.features.billing.test_minutes import delete_meeting, meter
from tests.features.billing.test_tokens import LIMITS, row, writer

PLANS = "/v1/admin/plans"
# Поля из upgrade/domain/contract.ts и settings/domain/billing-contract.ts кабинета.
PLANS_RESPONSE = {"plans", "current_plan_id", "seat", "effective_plan_id", "usage"}
PLAN = {"id", "name", "tagline", "audience", "seats", "price", "entitlements", "features",
        "highlighted"}  # fmt: skip
ENTITLEMENTS = {
    "meeting_minutes_per_month", "file_manager_gb", "knowledge_base_mb", "shared_workspace",
    "member_management", "centralized_billing", "sso", "admin_controls", "priority_support",
    "usage_analytics",
}  # fmt: skip
USAGE = {"week_start", "resets_at", "limits", "frontier"}
FRONTIER = {"extra_tokens", "models", "packs"}
TEAM = {"seats": {"min": 2, "max": 100}, "audience": "team"}
ENTERPRISE = {
    "audience": "enterprise", "custom_pricing": True,
    "price_monthly": {"RUB": 0, "USD": 0, "EUR": 0}, "price_yearly": {"RUB": 0, "USD": 0, "EUR": 0},
}  # fmt: skip


async def catalogue(people: PeopleBench) -> dict[str, str]:
    """Pro, Team and Enterprise on sale, and a plan off sale; their ids by slug."""
    bench = people.entitlements.catalogue
    drafts = {
        "pro": plan_draft("pro", sort_order=1),
        "team": plan_draft("team", sort_order=2, **TEAM),
        "enterprise": plan_draft("enterprise", sort_order=3, **ENTERPRISE),
        "legacy": plan_draft("legacy", sort_order=4, is_active=False),
    }
    return {slug: await created(bench, PLANS, draft) for slug, draft in drafts.items()}


async def plans_of(people: PeopleBench, person: tuple[Home, UUID]) -> dict[str, Any]:
    answer = await people.http.get("/v1/billing/plans", headers=bearer(person))
    assert answer.status_code == 200, answer.text
    body: dict[str, Any] = answer.json()
    return body


async def test_plans_come_in_the_cabinet_s_shape_and_the_account_s_currency(
    people: PeopleBench,
) -> None:
    ids = await catalogue(people)
    russian, german, unknown_eu, unknown_ru = (
        (Home.RU, uuid4()), (Home.EU, uuid4()), (Home.EU, uuid4()), (Home.RU, uuid4()),
    )  # fmt: skip
    people.countries.by_person |= {russian[1]: "RU", german[1]: "DE"}
    await people.entitlements.subscribe(german, (ids["legacy"], "legacy"))
    minutes = meter(people.entitlements)
    await delete_meeting(people.entitlements, minutes, russian, people.entitlements.clock.now)

    bodies = {
        name: await plans_of(people, person)
        for name, person in (
            ("ru", russian),
            ("de", german),
            ("eu", unknown_eu),
            ("rux", unknown_ru),
        )
    }
    refused = await people.http.get("/v1/billing/plans")

    ru, de = bodies["ru"], bodies["de"]
    assert set(ru) == PLANS_RESPONSE
    assert all(
        set(plan) == PLAN and set(plan["entitlements"]) == ENTITLEMENTS for plan in ru["plans"]
    )
    assert [plan["id"] for plan in ru["plans"]] == ["free", "pro", "team", "enterprise"]
    assert [plan["id"] for plan in de["plans"]][-1] == "legacy"
    currencies = {name: body["plans"][1]["price"]["currency"] for name, body in bodies.items()}
    assert currencies == {"ru": "RUB", "de": "EUR", "eu": "USD", "rux": "RUB"}
    assert ru["plans"][1]["price"] == {
        "amount_cents": 149_000,
        "currency": "RUB",
        "interval": "month",
    }
    assert ru["plans"][3]["price"] is None
    assert ru["plans"][2]["seats"] == {"min": 2, "max": 100}
    assert (ru["current_plan_id"], ru["effective_plan_id"], ru["seat"]) == ("free", "free", None)
    assert (de["current_plan_id"], de["effective_plan_id"]) == ("legacy", "legacy")
    _, end = month_window(people.entitlements.clock.now)
    assert ru["usage"]["used_minutes"] == 30.0
    assert ru["usage"]["limit_minutes"] == 120
    assert ru["usage"]["resets_at"].startswith(end.date().isoformat())
    assert de["usage"]["limit_minutes"] is None
    assert refused.status_code == 401


async def test_usage_shows_the_week_s_tokens_packs_and_frontier_models(people: PeopleBench) -> None:
    person = (Home.EU, uuid4())
    plan = await created(people.entitlements.catalogue, PLANS, plan_draft("pro", limits=LIMITS))
    await people.entitlements.subscribe(person, (plan, "pro"))
    costs, now = writer(people.entitlements), people.entitlements.clock.now
    await costs.write(row(person, now, 300))
    await costs.write(row(person, now, 600, model="probe/frontier-big"))
    await costs.write(row(person, now, 200, call=("standard", "interactive")))

    answer = await people.http.get("/v1/settings/usage", headers=bearer(person))

    body = answer.json()
    assert set(body) == USAGE
    assert set(body["frontier"]) == FRONTIER
    assert body["week_start"].startswith(week_window(now)[0].date().isoformat())
    limits = {item["tier"]: (item["used_tokens"], item["limit_tokens"]) for item in body["limits"]}
    assert limits == {"standard": (200, None), "frontier": (900, 1000)}
    assert body["frontier"]["extra_tokens"] == 0
    assert body["frontier"]["packs"] == []
    models = [(item["name"], item["used_tokens"]) for item in body["frontier"]["models"]]
    assert models == [("probe/frontier-big", 600), ("probe/chat", 300)]


async def test_a_sales_inquiry_is_stored_in_the_person_s_home_with_its_event(
    people: PeopleBench,
) -> None:
    person = (Home.RU, uuid4())
    form = {"work_email": " anna@acme.example ", "company": "Acme", "team_size": "51-200",
            "message": "SSO and invoices"}  # fmt: skip

    received = await people.http.post(
        "/v1/billing/sales-inquiry", json=form, headers=bearer(person)
    )
    refused = await people.http.post(
        "/v1/billing/sales-inquiry", json={**form, "team_size": "5"}, headers=bearer(person)
    )
    transactions = people.entitlements.homes.transactions

    assert (received.status_code, received.json()) == (202, {"status": "received"})
    assert refused.status_code == 422
    async with transactions.begin(TenancyScope(*person), read_only=True) as session:
        stored = (
            await session.execute(
                select(
                    SalesInquiryRecord.work_email,
                    SalesInquiryRecord.company,
                    SalesInquiryRecord.team_size,
                )
            )
        ).all()
        events = (
            await session.scalars(
                select(OutboxMessage.payload).where(
                    OutboxMessage.event_type == "billing.sales_inquiry.received"
                )
            )
        ).all()
    assert [tuple(item) for item in stored] == [("anna@acme.example", "Acme", "51-200")]
    assert [event["team_size"] for event in events] == ["51-200"]
