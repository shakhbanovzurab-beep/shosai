"""Billing's part of a person's export, transfer and erasure (ADR 0045 point 7)."""

from datetime import timedelta
from uuid import UUID, uuid4

from shosai.core.account_data.handlers import AccountRef
from shosai.core.kernel.homes import Home
from shosai.features.billing.application.account_data import BillingAccountData
from tests.features.billing.catalogue_bench import created, plan_draft
from tests.features.billing.entitlement_bench import EntitlementBench


async def test_export_transfer_and_erasure_cover_the_subscription_and_its_queue(
    entitlements: EntitlementBench,
) -> None:
    pro = await created(entitlements.catalogue, "/v1/admin/plans", plan_draft("pro"))
    start = await created(entitlements.catalogue, "/v1/admin/plans", plan_draft("start"))
    user_id = uuid4()
    await entitlements.subscribe(
        (Home.RU, user_id), (pro, "pro"), timedelta(days=5), ((UUID(start), 7),)
    )
    handler = BillingAccountData(entitlements.homes.transactions)
    russian, european = AccountRef(user_id, Home.RU), AccountRef(user_id, Home.EU)

    exported = {
        item.name: b"".join([chunk async for chunk in item.chunks])
        async for item in handler.export(russian)
    }
    await handler.copy(russian, Home.EU)
    await handler.copy(russian, Home.EU)
    same = await handler.manifest(russian) == await handler.manifest(european)
    await handler.erase(russian)
    await handler.purge(european)

    assert set(exported) == {
        "subscriptions.jsonl", "subscription_segments.jsonl", "usage_events.jsonl",
        "free_plan_devices.jsonl", "token_usage.jsonl", "premium_credit_ledger.jsonl",
    }  # fmt: skip
    assert pro.encode() in exported["subscriptions.jsonl"]
    assert b'"remaining_days": 7' in exported["subscription_segments.jsonl"]
    assert same
    assert await handler.remains(russian) == ()
    assert await handler.remains(european) == ()
