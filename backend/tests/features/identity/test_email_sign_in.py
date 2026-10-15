"""Sign-in by an emailed code (step 10b, ADR 0048): one path for a known person and a new one."""

import json

import httpx
from redis.asyncio import Redis

from shosai.core.crypto.key_ring import FernetKeyRing
from shosai.core.kernel.homes import Home
from tests.features.identity.registration_bench import registration_bench
from tests.features.identity.test_sign_in import EMAIL, account
from tests.harness.connections import fetch_rows
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot

NEWCOMER = "new.by.code@example.com"
WORLD = {"X-Country-Code": "DE"}
CONSENTS = {"personal_data": True, "cross_border": False, "marketing": False}
WRONG = "000000"


async def start(http: httpx.AsyncClient, email: str, headers: dict[str, str] | None = None) -> str:
    """Ask for a code; the sealed challenge."""
    answer = await http.post(
        "/v1/auth/email/start",
        json={"email": email, "language": "en", "next": "/app/notes"},
        headers=headers or {},
    )
    assert answer.status_code == 202, answer.text
    assert answer.json()["resend_after_seconds"] == 60
    challenge: str = answer.json()["challenge"]
    return challenge


async def codes(run_slot: RunSlot, key_ring: FernetKeyRing, home: Home) -> list[str]:
    """The sign-in codes mailed from a home, oldest first."""
    rows = await fetch_rows(
        run_slot.claimed.connections[home],
        "SELECT secrets FROM email_messages WHERE template = 'identity.sign_in_code' "
        "ORDER BY created_at, id",
    )
    return [json.loads(key_ring.decrypt(row["secrets"]))["code"] for row in rows]


async def verify(http: httpx.AsyncClient, challenge: str, code: str) -> httpx.Response:
    return await http.post("/v1/auth/email/verify", json={"challenge": challenge, "code": code})


async def test_a_known_person_signs_in_by_the_code(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        await account(bench, run_slot, Home.RU)
        challenge = await start(bench.http, EMAIL, WORLD)
        [code] = await codes(run_slot, bench.key_ring, Home.RU)
        signed_in = await verify(bench.http, challenge, code)

    assert signed_in.status_code == 200, signed_in.text
    body = signed_in.json()
    assert (body["consent_ticket"], body["next"]) == (None, "/app/notes")
    assert body["session"]["access_token"]
    assert signed_in.cookies.get("meetassist_refresh")
    assert await codes(run_slot, bench.key_ring, Home.EU) == []


async def test_a_new_person_gets_an_account_in_the_home_of_the_confirmed_country(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        challenge = await start(bench.http, NEWCOMER, WORLD)
        [code] = await codes(run_slot, bench.key_ring, Home.EU)
        verified = await verify(bench.http, challenge, code)
        ticket = verified.json()["consent_ticket"]
        registered = await bench.http.post(
            "/v1/auth/social/register",
            json={"ticket": ticket, "country": "NL", "language": "nl", "consents": CONSENTS},
        )

    assert (verified.status_code, verified.json()["session"]) == (200, None)
    assert registered.status_code == 200, registered.text
    assert registered.json()["next"] == "/app/notes"
    [user] = await fetch_rows(
        run_slot.claimed.connections[Home.EU],
        "SELECT email, password_hash, email_verified_at IS NOT NULL AS verified FROM users",
    )
    assert (user["email"], user["password_hash"], user["verified"]) == (NEWCOMER, None, True)
    assert (
        await fetch_rows(run_slot.claimed.connections[Home.EU], "SELECT 1 FROM user_identities")
        == []
    )


async def test_a_stranger_from_an_unknown_country_is_mailed_from_the_russian_home(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        await start(bench.http, NEWCOMER)

    assert len(await codes(run_slot, bench.key_ring, Home.RU)) == 1
    assert await codes(run_slot, bench.key_ring, Home.EU) == []


async def test_the_start_answer_does_not_tell_whether_an_account_exists(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        await account(bench, run_slot, Home.RU)
        known = await bench.http.post("/v1/auth/email/start", json={"email": EMAIL})
        unknown = await bench.http.post("/v1/auth/email/start", json={"email": NEWCOMER})

    assert known.status_code == unknown.status_code == 202
    assert set(known.json()) == set(unknown.json())
    assert known.json()["resend_after_seconds"] == unknown.json()["resend_after_seconds"]


async def test_five_wrong_codes_end_the_challenge(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        challenge = await start(bench.http, NEWCOMER, WORLD)
        [code] = await codes(run_slot, bench.key_ring, Home.EU)
        wrong = [(await verify(bench.http, challenge, WRONG)).json() for _ in range(5)]
        late = await verify(bench.http, challenge, code)

    assert [answer["error"]["code"] for answer in wrong] == ["invalid_code"] * 4 + ["code_locked"]
    assert (late.status_code, late.json()["error"]["code"]) == (400, "invalid_code")


async def test_a_code_works_once(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        await account(bench, run_slot, Home.RU)
        challenge = await start(bench.http, EMAIL)
        [code] = await codes(run_slot, bench.key_ring, Home.RU)
        first = await verify(bench.http, challenge, code)
        second = await verify(bench.http, challenge, code)
        too_soon = await bench.http.post("/v1/auth/email/resend", json={"challenge": challenge})

    assert first.status_code == 200
    assert (second.status_code, second.json()["error"]["code"]) == (400, "invalid_code")
    assert (too_soon.status_code, too_soon.json()["error"]["code"]) == (400, "invalid_code")


async def test_a_new_code_comes_no_sooner_than_a_minute(
    homes: DatabaseAccess, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        challenge = await start(bench.http, NEWCOMER, WORLD)
        again = await bench.http.post("/v1/auth/email/resend", json={"challenge": challenge})

    assert (again.status_code, again.json()["error"]["code"]) == (429, "resend_too_soon")
    assert 0 < again.json()["error"]["params"]["retry_after_seconds"] <= 60


async def test_valkey_holds_no_address(
    homes: DatabaseAccess, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        challenge = await start(bench.http, NEWCOMER, WORLD)
        keys = [key async for key in valkey.scan_iter(match="*email_challenge*")]
        values = [await valkey.hgetall(key) for key in keys]

    assert len(keys) == 1
    dumped = json.dumps({str(k): str(v) for value in values for k, v in value.items()})
    assert "example.com" not in dumped
    assert NEWCOMER not in challenge
