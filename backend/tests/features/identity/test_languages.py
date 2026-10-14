"""The cabinet's 16 languages in identity: kept by their codes, shown to desktop apps in theirs."""

import pytest
from redis.asyncio import Redis
from sqlalchemy.exc import IntegrityError

from shosai.core.kernel.homes import Home
from shosai.core.kernel.ids import new_id
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.identity.infrastructure.records import User
from tests.features.identity.registration_bench import registration_bench
from tests.features.identity.test_profile import signed_in
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot


async def test_a_language_is_kept_by_the_cabinet_code_and_desktop_apps_read_their_own(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        headers = await signed_in(bench, run_slot)
        seen = []
        for chosen in ("nl", "pt", "zh-TW", "pt-BR", "en"):
            kept = await bench.http.patch("/v1/me", headers=headers, json={"language": chosen})
            native = await bench.http.get("/v1/auth/me", headers=headers)
            seen.append((kept.json()["language"], native.json()["language"]))
        thai = await bench.http.patch("/v1/me", headers=headers, json={"language": "th"})

    assert seen == [
        ("nl", None), ("pt-BR", "pt"), ("zh-Hant", "zh"), ("pt-BR", "pt"), ("en", "en"),
    ]  # fmt: skip
    assert (thai.status_code, thai.json()["error"]["code"]) == (422, "unsupported_language")


async def test_the_database_refuses_a_language_outside_the_platform(homes: DatabaseAccess) -> None:
    user_id = new_id()

    with pytest.raises(IntegrityError, match="language_known"):
        async with homes.transactions.begin(TenancyScope(Home.RU, user_id)) as session:
            session.add(User(id=user_id, email="a@example.com", full_name="A", language="th"))
