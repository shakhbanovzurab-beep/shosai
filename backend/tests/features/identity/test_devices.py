"""The person's devices: list, end one, end the others (step 4)."""

from uuid import UUID

from redis.asyncio import Redis

from shosai.core.kernel.homes import Home
from tests.features.identity.registration_bench import (
    RegistrationBench,
    form,
    mailed_codes,
    register,
    registration_bench,
)
from tests.features.identity.test_sign_in import account, login
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot


def bearer(token: object) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def devices(bench: RegistrationBench, token: object) -> list[dict[str, object]]:
    answer = await bench.http.get("/v1/me/devices", headers=bearer(token))
    assert answer.status_code == 200, answer.text
    items: list[dict[str, object]] = answer.json()["items"]
    return items


async def other_account_session(bench: RegistrationBench, run_slot: RunSlot) -> UUID:
    """A session id of another person."""
    registration_id = await register(bench.http, form("someone.else@example.com"))
    code = (await mailed_codes(run_slot, bench.key_ring, Home.RU))[-1]
    verified = await bench.http.post(
        "/v1/auth/register/verify", json={"registration_id": str(registration_id), "code": code}
    )
    bench.http.cookies.clear()
    token = verified.json()["access_token"]
    [item] = await devices(bench, token)
    return UUID(str(item["id"]))


async def test_the_list_shows_live_sessions_and_marks_the_current_one(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        await account(bench, run_slot)
        await login(bench)
        token = (await login(bench))["access_token"]
        items = await devices(bench, token)

    # Подтверждение регистрации и два входа: три устройства, текущее — последнее.
    assert len(items) == 3
    assert [item["current"] for item in items] == [True, False, False]
    assert {item["client_kind"] for item in items} == {"web"}


async def test_ending_a_device_stops_its_live_token_and_another_persons_is_404(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        await account(bench, run_slot)
        laptop = (await login(bench))["access_token"]
        phone = (await login(bench))["access_token"]
        [_, laptop_item, _] = await devices(bench, phone)
        foreign = await other_account_session(bench, run_slot)
        ended = await bench.http.delete(
            f"/v1/me/devices/{laptop_item['id']}", headers=bearer(phone)
        )
        laptop_after = await bench.http.get("/v1/auth/me", headers=bearer(laptop))
        phone_after = await bench.http.get("/v1/auth/me", headers=bearer(phone))
        not_mine = await bench.http.delete(f"/v1/me/devices/{foreign}", headers=bearer(phone))

    assert ended.status_code == 204
    assert (laptop_after.status_code, laptop_after.json()["detail"]) == (401, "Token revoked")
    assert phone_after.status_code == 200
    assert (not_mine.status_code, not_mine.json()["error"]["code"]) == (404, "device_not_found")


async def test_signing_out_the_others_keeps_this_device(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        await account(bench, run_slot)
        other = (await login(bench))["access_token"]
        this = (await login(bench))["access_token"]
        answer = await bench.http.post("/v1/me/devices/sign-out-others", headers=bearer(this))
        left = await devices(bench, this)
        other_after = await bench.http.get("/v1/auth/me", headers=bearer(other))

    assert answer.json() == {"ended": 2}
    assert [item["current"] for item in left] == [True]
    assert other_after.status_code == 401
