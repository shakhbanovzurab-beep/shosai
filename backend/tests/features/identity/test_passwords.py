"""Forgot, reset and change: one use, 60 minutes, every other session ends (step 3b)."""

import json
from urllib.parse import parse_qs, urlsplit

from redis.asyncio import Redis

from shosai.core.kernel.homes import Home
from tests.features.identity.registration_bench import RegistrationBench, registration_bench
from tests.features.identity.test_sign_in import EMAIL, PASSWORD, account, csrf, login
from tests.harness.connections import fetch_rows
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot

NEW_PASSWORD = "a brand new passphrase"


async def reset_links(run_slot: RunSlot, bench: RegistrationBench) -> list[str]:
    """The tokens of the reset links mailed from the Russian home, oldest first."""
    rows = await fetch_rows(
        run_slot.claimed.connections[Home.RU],
        "SELECT secrets FROM email_messages WHERE template = 'identity.password_reset' "
        "ORDER BY created_at, id",
    )
    links = [json.loads(bench.key_ring.decrypt(row["secrets"]))["link"] for row in rows]
    return [parse_qs(urlsplit(link).query)["token"][0] for link in links]


async def forgot(bench: RegistrationBench, email: str = EMAIL) -> int:
    answer = await bench.http.post("/v1/auth/password/forgot", json={"email": email})
    return answer.status_code


async def reset(bench: RegistrationBench, token: str) -> tuple[int, str | None]:
    answer = await bench.http.post(
        "/v1/auth/password/reset", json={"token": token, "password": NEW_PASSWORD}
    )
    code = None if answer.status_code == 204 else answer.json()["error"]["code"]
    return answer.status_code, code


async def test_a_link_works_once_and_only_for_an_existing_account(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        await account(bench, run_slot)
        answers = (await forgot(bench), await forgot(bench, "ghost@example.com"))
        [token] = await reset_links(run_slot, bench)
        first = await reset(bench, token)
        second = await reset(bench, token)
        old = await bench.http.post("/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})
        new = await bench.http.post(
            "/v1/auth/login", json={"email": EMAIL, "password": NEW_PASSWORD}
        )

    assert answers == (202, 202)
    assert first == (204, None)
    assert second == (400, "invalid_token")
    assert (old.status_code, new.status_code) == (401, 200)


async def test_a_new_link_voids_the_older_and_a_link_expires(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        await account(bench, run_slot)
        await forgot(bench)
        await forgot(bench)
        older, newer = await reset_links(run_slot, bench)
        voided = await reset(bench, older)
        await run_slot.claimed.connections[Home.RU].execute(
            "UPDATE password_reset_tokens SET expires_at = now() - interval '1 second'"
        )
        expired = await reset(bench, newer)

    assert voided == expired == (400, "invalid_token")


async def test_a_reset_signs_every_session_out_on_its_next_request(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        await account(bench, run_slot)
        token = (await login(bench))["access_token"]
        headers = csrf(bench)
        await forgot(bench)
        [link] = await reset_links(run_slot, bench)
        await reset(bench, link)
        me = await bench.http.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        refreshed = await bench.http.post("/v1/auth/refresh", headers=headers)

    assert (me.status_code, me.json()["detail"]) == (401, "Token revoked")
    assert (refreshed.status_code, refreshed.json()["detail"]) == (401, "Token revoked")


async def test_a_change_needs_the_current_password_and_keeps_only_this_device(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        await account(bench, run_slot)
        old_token = (await login(bench))["access_token"]
        bearer = {"Authorization": f"Bearer {old_token}"}
        wrong = await bench.http.post(
            "/v1/me/password",
            json={"current_password": "nope", "new_password": NEW_PASSWORD},
            headers=bearer,
        )
        changed = await bench.http.post(
            "/v1/me/password",
            json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
            headers=bearer,
        )
        new_token = changed.json()["access_token"]
        with_old = await bench.http.get("/v1/auth/me", headers=bearer)
        with_new = await bench.http.get(
            "/v1/auth/me", headers={"Authorization": f"Bearer {new_token}"}
        )

    assert (wrong.status_code, wrong.json()["error"]["code"]) == (403, "wrong_password")
    assert changed.status_code == 200
    assert with_old.status_code == 401
    assert with_new.status_code == 200
    families = await fetch_rows(
        run_slot.claimed.connections[Home.RU],
        "SELECT revoke_reason FROM refresh_sessions ORDER BY created_at",
    )
    assert [row["revoke_reason"] for row in families] == ["password_change"] * 2 + [None]
