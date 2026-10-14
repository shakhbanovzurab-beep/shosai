"""Sign-in, refresh, logout and `/v1/auth/me` with the draft's contract (step 3a)."""

from uuid import UUID

import pytest
from psycopg import sql
from redis.asyncio import Redis

from shosai.core.kernel.homes import Home
from shosai.features.identity.domain.accounts import AccountState
from shosai.features.identity.infrastructure import directory as directory_module
from shosai.features.identity.infrastructure.account_markers import AccountMarker
from tests.features.identity.registration_bench import (
    BenchOptions,
    RegistrationBench,
    eu_unreachable,
    form,
    mailed_codes,
    register,
    registration_bench,
)
from tests.harness.connections import fetch_rows
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot

EMAIL = "signin@example.com"
PASSWORD = "correct horse battery"


async def account(
    bench: RegistrationBench, run_slot: RunSlot, home: Home = Home.RU, email: str = EMAIL
) -> UUID:
    """A registered and confirmed account; its cookies are dropped."""
    registration_id = await register(bench.http, form(email, "RU" if home is Home.RU else "DE"))
    code = (await mailed_codes(run_slot, bench.key_ring, home))[-1]
    verified = await bench.http.post(
        "/v1/auth/register/verify", json={"registration_id": str(registration_id), "code": code}
    )
    assert verified.status_code == 201, verified.text
    assert verified.cookies.get("meetassist_refresh")
    bench.http.cookies.clear()
    return UUID(verified.json()["user_id"])


async def login(bench: RegistrationBench, password: str = PASSWORD) -> dict[str, object]:
    answer = await bench.http.post("/v1/auth/login", json={"email": EMAIL, "password": password})
    assert answer.status_code == 200, answer.text
    body: dict[str, object] = answer.json()
    return body


async def last_family(run_slot: RunSlot) -> dict[str, object]:
    """The newest refresh family of the Russian home (the sign-in's, after verification's)."""
    rows = await fetch_rows(
        run_slot.claimed.connections[Home.RU],
        "SELECT generation, revoke_reason FROM refresh_sessions ORDER BY created_at",
    )
    return dict(rows[-1])


def csrf(bench: RegistrationBench) -> dict[str, str]:
    return {"X-CSRF-Token": bench.http.cookies.get("meetassist_csrf") or ""}


async def detail_of(
    bench: RegistrationBench,
    path: str,
    json: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, object]:
    answer = await bench.http.post(path, json=json, headers=headers)
    return answer.status_code, answer.json().get("detail")


async def refresh_with(
    bench: RegistrationBench, refresh_token: str, csrf_token: str
) -> tuple[int, object]:
    """Refresh with exactly these cookies, as another tab or a thief would."""
    bench.http.cookies.clear()
    cookie = f"meetassist_refresh={refresh_token}; meetassist_csrf={csrf_token}"
    answer = await bench.http.post(
        "/v1/auth/refresh", headers={"Cookie": cookie, "X-CSRF-Token": csrf_token}
    )
    return answer.status_code, answer.json().get("detail")


async def test_sign_in_answers_the_draft_shape_and_sets_both_cookies(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        user_id = await account(bench, run_slot)
        answer = await bench.http.post(
            "/v1/auth/login", json={"email": EMAIL.upper(), "password": PASSWORD}
        )
        token = answer.json()["access_token"]
        me = await bench.http.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert answer.status_code == 200
    assert set(answer.json()) == {"access_token", "expires_in", "token_type", "csrf_token"}
    assert (answer.json()["expires_in"], answer.json()["token_type"]) == (1800, "Bearer")
    cookies = answer.headers.get_list("set-cookie")
    refresh = next(cookie for cookie in cookies if cookie.startswith("meetassist_refresh="))
    assert {"HttpOnly", "Path=/v1/auth", "Secure"} <= {part.strip() for part in refresh.split(";")}
    assert any(
        cookie.startswith(f"meetassist_csrf={answer.json()['csrf_token']}") for cookie in cookies
    )
    assert me.status_code == 200
    body = me.json()
    assert len(body) == 23
    assert (body["id"], body["email"], body["role"], body["status"]) == (
        str(user_id),
        EMAIL,
        "user",
        "active",
    )
    assert (body["subscription"], body["quota"], body["memory_enabled"]) == (None, None, True)
    events = await fetch_rows(
        run_slot.claimed.connections[Home.RU], "SELECT outcome FROM login_events"
    )
    assert [row["outcome"] for row in events] == ["success"]


async def test_a_wrong_password_and_an_unknown_address_look_the_same(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        await account(bench, run_slot)
        wrong = await detail_of(bench, "/v1/auth/login", json={"email": EMAIL, "password": "nope"})
        unknown = await detail_of(
            bench, "/v1/auth/login", json={"email": "ghost@example.com", "password": "nope"}
        )

    assert wrong == unknown == (401, "Invalid email or password")
    events = await fetch_rows(
        run_slot.claimed.connections[Home.RU], "SELECT outcome FROM login_events"
    )
    assert [row["outcome"] for row in events] == ["wrong_password"]


async def test_the_password_of_a_pending_registration_asks_for_the_code(
    homes: DatabaseAccess, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        await register(bench.http, form(EMAIL))
        answer = await detail_of(
            bench, "/v1/auth/login", json={"email": EMAIL, "password": PASSWORD}
        )

    assert answer == (403, "email_not_verified")


@pytest.mark.parametrize("state", [AccountState.BANNED, AccountState.FROZEN])
async def test_a_blocked_account_is_told_only_after_the_right_password(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis, state: AccountState
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        await account(bench, run_slot)
        await run_slot.claimed.connections[Home.RU].execute(
            sql.SQL("UPDATE users SET state = {}").format(sql.Literal(state.value))
        )
        wrong = await detail_of(bench, "/v1/auth/login", json={"email": EMAIL, "password": "nope"})
        right = await detail_of(
            bench, "/v1/auth/login", json={"email": EMAIL, "password": PASSWORD}
        )

    assert wrong == (401, "Invalid email or password")
    assert right == (403, f"account_{state.value}")


async def test_refresh_needs_its_cookie_and_the_csrf_header(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        await account(bench, run_slot)
        first = await login(bench)
        mismatch = await detail_of(bench, "/v1/auth/refresh", headers={"X-CSRF-Token": "forged"})
        before = bench.http.cookies.get("meetassist_refresh")
        rotated = await bench.http.post("/v1/auth/refresh", headers=csrf(bench))
        after = bench.http.cookies.get("meetassist_refresh")
        bench.http.cookies.clear()
        missing = await detail_of(bench, "/v1/auth/refresh")

    assert mismatch == (403, "CSRF mismatch")
    assert rotated.status_code == 200
    assert rotated.json()["csrf_token"] == first["csrf_token"]
    assert rotated.json()["access_token"]
    assert before != after
    assert missing == (401, "Missing refresh cookie")


async def test_a_replayed_old_token_revokes_the_family_and_the_revocation_holds(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        await account(bench, run_slot)
        await login(bench)
        stolen = bench.http.cookies.get("meetassist_refresh") or ""
        csrf_token = bench.http.cookies.get("meetassist_csrf") or ""
        await bench.http.post("/v1/auth/refresh", headers=csrf(bench))
        current = bench.http.cookies.get("meetassist_refresh") or ""
        await run_slot.claimed.connections[Home.RU].execute(
            "UPDATE refresh_sessions SET rotated_at = now() - interval '11 seconds'"
        )
        replay = await refresh_with(bench, stolen, csrf_token)
        after = await refresh_with(bench, current, csrf_token)

    assert replay == (401, "Invalid refresh token")
    assert after == (401, "Token revoked")
    family = await last_family(run_slot)
    assert family["revoke_reason"] == "reuse"


async def test_two_tabs_refreshing_at_once_both_stay_signed_in(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        await account(bench, run_slot)
        await login(bench)
        token = bench.http.cookies.get("meetassist_refresh") or ""
        csrf_token = bench.http.cookies.get("meetassist_csrf") or ""
        tabs = [await refresh_with(bench, token, csrf_token) for _ in range(2)]

    assert [tab[0] for tab in tabs] == [200, 200]
    family = await last_family(run_slot)
    assert (family["generation"], family["revoke_reason"]) == (1, None)


async def test_a_ban_reaches_a_live_access_token_on_its_next_request(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        user_id = await account(bench, run_slot)
        token = (await login(bench))["access_token"]
        bearer = {"Authorization": f"Bearer {token}"}
        before = await bench.http.get("/v1/auth/me", headers=bearer)
        await bench.markers.write(user_id, AccountMarker(0, AccountState.BANNED))
        banned = await bench.http.get("/v1/auth/me", headers=bearer)
        await bench.markers.write(user_id, AccountMarker(1, AccountState.ACTIVE))
        revoked = await bench.http.get("/v1/auth/me", headers=bearer)
        missing = await bench.http.get("/v1/auth/me")

    assert before.status_code == 200
    assert (banned.status_code, banned.json()["detail"]) == (403, "account_banned")
    assert (revoked.status_code, revoked.json()["detail"]) == (401, "Token revoked")
    assert (missing.status_code, missing.json()["detail"]) == (401, "Missing Bearer token")


async def test_refresh_reads_the_home_so_a_version_bump_ends_the_family(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        await account(bench, run_slot)
        await login(bench)
        await run_slot.claimed.connections[Home.RU].execute(
            "UPDATE users SET token_version = token_version + 1"
        )
        answer = await detail_of(bench, "/v1/auth/refresh", headers=csrf(bench))

    assert answer == (401, "Token revoked")


async def test_logout_ends_the_family_of_the_cookie_or_of_a_body_token(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        await account(bench, run_slot)
        await login(bench)
        by_cookie = await bench.http.post("/v1/auth/logout")
        await login(bench)
        desktop_token = bench.http.cookies.get("meetassist_refresh") or ""
        bench.http.cookies.clear()
        by_body = await bench.http.post("/v1/auth/logout", json={"refresh_token": desktop_token})
        nothing = await bench.http.post("/v1/auth/logout")

    assert by_cookie.json() == by_body.json() == nothing.json() == {"ok": True}
    assert any("meetassist_refresh=" in c for c in by_cookie.headers.get_list("set-cookie"))
    families = await fetch_rows(
        run_slot.claimed.connections[Home.RU],
        "SELECT revoke_reason FROM refresh_sessions ORDER BY created_at",
    )
    # Первая семья — сессия подтверждения регистрации: её никто не закрывал.
    assert [row["revoke_reason"] for row in families] == [None, "logout", "logout"]


async def test_sign_in_uses_the_last_directory_copy_when_the_eu_home_is_down(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        await account(bench, run_slot)
        await login(bench)
    monkeypatch.setattr(directory_module, "FRESH_FOR", directory_module.FRESH_FOR * 0)
    async with registration_bench(
        homes.transactions, valkey, redis_cache, BenchOptions(directory_transactions=eu_unreachable)
    ) as outage:
        answer = await outage.http.post(
            "/v1/auth/login", json={"email": EMAIL, "password": PASSWORD}
        )

    assert answer.status_code == 200
