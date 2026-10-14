"""Desktop sign-in through the browser: one-time codes, PKCE, the desktop refresh (step 4)."""

import asyncio
import hashlib
from base64 import urlsafe_b64encode

from redis.asyncio import Redis

from shosai.core.kernel.homes import Home
from shosai.core.kernel.ids import new_id
from shosai.features.identity.infrastructure.desktop_codes import DesktopCodes, DesktopGrant
from tests.features.identity.registration_bench import RegistrationBench, registration_bench
from tests.features.identity.test_sign_in import account, login
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot

VERIFIER = "a-verifier-of-the-macos-client-at-least-43-characters-long"
CHALLENGE = urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest()).rstrip(b"=").decode()


async def code_for(bench: RegistrationBench, challenge: str | None = None) -> str:
    """A desktop code issued to the signed-in browser of the bench."""
    token = (await login(bench))["access_token"]
    body = {"code_challenge": challenge, "code_challenge_method": "S256"} if challenge else None
    answer = await bench.http.post(
        "/v1/auth/desktop/code", json=body, headers={"Authorization": f"Bearer {token}"}
    )
    assert answer.status_code == 200, answer.text
    assert answer.json()["expires_in"] == 120
    return str(answer.json()["code"])


async def exchange(bench: RegistrationBench, body: dict[str, str]) -> tuple[int, dict[str, object]]:
    answer = await bench.http.post("/v1/auth/desktop/exchange", json=body)
    return answer.status_code, answer.json()


async def test_the_windows_request_exchanges_a_code_once(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        await account(bench, run_slot)
        code = await code_for(bench)
        # Windows 1.4.5 шлёт только код (contracts/draft/consumers.json, AuthClient.cs:153).
        first = await exchange(bench, {"code": code})
        again = await exchange(bench, {"code": code})
        me = await bench.http.get(
            "/v1/auth/me", headers={"Authorization": f"Bearer {first[1]['access_token']}"}
        )

    assert first[0] == 200
    assert set(first[1]) == {"access_token", "refresh_token", "expires_in", "token_type"}
    assert again == (401, again[1])
    assert again[1]["detail"] == "invalid_or_expired_code"
    assert me.status_code == 200


async def test_of_twenty_simultaneous_takes_exactly_one_gets_the_code(valkey: Redis) -> None:
    # HTTP-обмен ограничен 10 в минуту с адреса: атомарность проверяется там, где она есть.
    codes = DesktopCodes(valkey)
    code = await codes.issue(DesktopGrant(new_id(), Home.RU, None))

    grants = await asyncio.gather(*(codes.take(code) for _ in range(20)))

    assert sum(grant is not None for grant in grants) == 1


async def test_a_code_with_a_challenge_needs_its_verifier(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        await account(bench, run_slot)
        without = await exchange(bench, {"code": await code_for(bench, CHALLENGE)})
        wrong = await exchange(
            bench, {"code": await code_for(bench, CHALLENGE), "code_verifier": "x" * 43}
        )
        right = await exchange(
            bench, {"code": await code_for(bench, CHALLENGE), "code_verifier": VERIFIER}
        )

    assert [without[0], wrong[0], right[0]] == [401, 401, 200]


async def test_a_challenge_must_be_s256(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        await account(bench, run_slot)
        token = (await login(bench))["access_token"]
        answer = await bench.http.post(
            "/v1/auth/desktop/code",
            json={"code_challenge": CHALLENGE, "code_challenge_method": "plain"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert (answer.status_code, answer.json()["error"]["code"]) == (422, "invalid_code_challenge")


async def test_the_desktop_refresh_rotates_and_speaks_its_own_details(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        await account(bench, run_slot)
        _, tokens = await exchange(bench, {"code": await code_for(bench)})
        first = str(tokens["refresh_token"])
        rotated = await bench.http.post("/v1/auth/desktop/refresh", json={"refresh_token": first})
        await run_slot.claimed.connections[Home.RU].execute(
            "UPDATE refresh_sessions SET rotated_at = now() - interval '11 seconds'"
        )
        replay = await bench.http.post("/v1/auth/desktop/refresh", json={"refresh_token": first})
        garbage = await bench.http.post(
            "/v1/auth/desktop/refresh", json={"refresh_token": "not-a-token"}
        )

    assert rotated.status_code == 200
    assert rotated.json()["refresh_token"] != first
    assert (replay.status_code, replay.json()["detail"]) == (401, "invalid_refresh")
    assert (garbage.status_code, garbage.json()["detail"]) == (401, "invalid_refresh")
