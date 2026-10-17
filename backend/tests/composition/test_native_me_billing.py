"""The native `/v1/auth/me` with billing's fields, as the shipped clients decode it (step 3).

The composed api app answers a person with a paid subscription; the body passes the
clients' decoding of `AuthUser` and carries the plan's tariff, unlimited minutes and the
teleprompter of a paid plan. A person without a subscription gets no card and the Free
plan's minutes.
"""

from redis.asyncio import Redis

from shosai.composition.features import FEATURES
from shosai.core.kernel.homes import Home
from tests.composition.native_clients import decode_auth_user, decode_token_response
from tests.composition.test_native_sign_in_replay import KEYS, LOGIN, bearer, connection
from tests.composition.test_public_routes import compose
from tests.features.billing.catalogue_bench import created, plan_draft
from tests.features.billing.entitlement_bench import EntitlementBench
from tests.features.identity.registration_bench import registration_bench
from tests.features.identity.test_sign_in import EMAIL, account
from tests.harness.run_slot import RunSlot
from tests.harness.settings import HarnessSettings


async def test_the_native_me_carries_billing_s_fields_in_the_draft_s_shapes(
    run_slot: RunSlot,
    harness_settings: HarnessSettings,
    entitlements: EntitlementBench,
    valkey: Redis,
    redis_cache: Redis,
) -> None:
    async with registration_bench(entitlements.homes.transactions, valkey, redis_cache) as bench:
        user_id = await account(bench, run_slot)
    async with (
        compose(run_slot, harness_settings, FEATURES, KEYS) as apps,
        connection(apps["api"]) as client,
    ):
        access = decode_token_response((await client.post("/v1/auth/login", json=LOGIN)).json())
        free = (await client.get("/v1/auth/me", headers=bearer(access))).json()
        plan_id = await created(entitlements.catalogue, "/v1/admin/plans", plan_draft("pro"))
        await entitlements.subscribe((Home.RU, user_id), (plan_id, "pro"))
        paid = (await client.get("/v1/auth/me", headers=bearer(access))).json()

    assert decode_auth_user(free) == EMAIL
    assert free["subscription"] is None
    assert (free["quota"]["unlimited"], free["quota"]["limit_minutes"]) == (False, 120)
    assert free["features"]["teleprompter"] is False
    assert decode_auth_user(paid) == EMAIL
    card = paid["subscription"]
    assert (card["status"], card["days_left"], card["bonus_minutes"]) == ("active", 30, 0)
    tariff = card["tariff"]
    assert (tariff["id"], tariff["code"], tariff["price_rub"], tariff["period_days"]) == (
        plan_id, "pro", 1490, 31,
    )  # fmt: skip
    assert tariff["storage_limit_bytes"] == 100 * 1024**3
    assert paid["quota"] == {
        "unlimited": True, "limit_minutes": None, "bonus_minutes": 0,
        "used_minutes": None, "remaining_minutes": None, "exhausted": False,
    }  # fmt: skip
    assert paid["features"]["teleprompter"] is True
