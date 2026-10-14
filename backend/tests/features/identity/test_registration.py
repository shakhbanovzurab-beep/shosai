"""Registration across homes: one account per address, nothing personal in the EU (step 2)."""

import asyncio
from uuid import UUID

from psycopg import sql
from redis.asyncio import Redis

from shosai.core.kernel.homes import Home
from shosai.features.identity.domain.registration import MAX_CODE_ATTEMPTS
from tests.features.identity.registration_bench import (
    eu_unreachable,
    form,
    mailed_codes,
    register,
    registration_bench,
)
from tests.harness.connections import fetch_rows
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot

EMAIL = "anna.petrova@example.com"


async def rows(run_slot: RunSlot, home: Home, query: str | sql.Composed) -> list[dict[str, object]]:
    """The rows of a query in a home, as plain dictionaries."""
    return [dict(row) for row in await fetch_rows(run_slot.claimed.connections[home], query)]


async def eu_text(run_slot: RunSlot) -> str:
    """Every row of every application table of the EU home, as text."""
    tables = await rows(
        run_slot,
        Home.EU,
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public' "
        "AND tablename <> 'alembic_version'",
    )
    dumps = [
        await rows(
            run_slot,
            Home.EU,
            sql.SQL("SELECT row_to_json(t)::text AS row FROM {} t").format(
                sql.Identifier(str(table["tablename"]))
            ),
        )
        for table in tables
    ]
    return "\n".join(str(row["row"]) for dump in dumps for row in dump)


async def test_a_russian_registration_creates_one_account_in_its_home_only(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        registration_id = await register(bench.http, form(EMAIL))
        [code] = await mailed_codes(run_slot, bench.key_ring, Home.RU)
        verified = await bench.http.post(
            "/v1/auth/register/verify", json={"registration_id": str(registration_id), "code": code}
        )

    assert verified.status_code == 201, verified.text
    user_id = verified.json()["user_id"]
    users = await rows(run_slot, Home.RU, "SELECT id::text, email, state, country FROM users")
    assert users == [{"id": user_id, "email": EMAIL, "state": "active", "country": "RU"}]
    consents = await rows(
        run_slot, Home.RU, "SELECT kind, granted FROM user_consents ORDER BY kind"
    )
    assert consents == [
        {"kind": "cross_border", "granted": True},
        {"kind": "marketing", "granted": False},
        {"kind": "personal_data", "granted": True},
    ]
    assert await rows(run_slot, Home.RU, "SELECT id FROM pending_registrations") == []
    [event] = await rows(run_slot, Home.RU, "SELECT event_type FROM outbox_messages")
    assert event == {"event_type": "identity.account.registered"}
    [entry] = await rows(
        run_slot, Home.EU, "SELECT user_id::text, home, state FROM directory_entries"
    )
    assert entry == {"user_id": user_id, "home": "ru", "state": "active"}
    # В доме ЕС от русского аккаунта — только HMAC, id и дом: ни адреса, ни имени.
    eu = await eu_text(run_slot)
    assert EMAIL not in eu
    assert "Anna" not in eu
    assert await rows(run_slot, Home.EU, "SELECT id FROM users") == []


async def test_two_homes_confirming_one_address_at_once_make_one_account(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        russian = await register(bench.http, form(EMAIL, "RU"))
        german = await register(bench.http, form(EMAIL, "DE"))
        [ru_code] = await mailed_codes(run_slot, bench.key_ring, Home.RU)
        [eu_code] = await mailed_codes(run_slot, bench.key_ring, Home.EU)
        answers = await asyncio.gather(
            bench.http.post(
                "/v1/auth/register/verify", json={"registration_id": str(russian), "code": ru_code}
            ),
            bench.http.post(
                "/v1/auth/register/verify", json={"registration_id": str(german), "code": eu_code}
            ),
        )

    assert sorted(answer.status_code for answer in answers) == [201, 409]
    loser = next(answer for answer in answers if answer.status_code == 409)
    assert loser.json()["error"]["code"] == "email_registered"
    accounts = [
        *await rows(run_slot, Home.RU, "SELECT id FROM users"),
        *await rows(run_slot, Home.EU, "SELECT id FROM users"),
    ]
    assert len(accounts) == 1
    assert len(await rows(run_slot, Home.EU, "SELECT 1 AS one FROM directory_entries")) == 1


async def test_a_second_registration_cannot_take_over_the_first(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        owner = await register(bench.http, form(EMAIL, password="owner password 1"))
        intruder = await register(bench.http, form(EMAIL, password="intruder password"))
        owner_code, intruder_code = await mailed_codes(run_slot, bench.key_ring, Home.RU)
        crossed = await bench.http.post(
            "/v1/auth/register/verify",
            json={"registration_id": str(owner), "code": intruder_code},
        )
        confirmed = await bench.http.post(
            "/v1/auth/register/verify", json={"registration_id": str(owner), "code": owner_code}
        )
        [stored] = await rows(run_slot, Home.RU, "SELECT password_hash FROM users")
        owner_password = await bench.services.hasher.verify(
            "owner password 1", str(stored["password_hash"])
        )

    assert owner != intruder
    assert crossed.status_code == 400
    assert confirmed.status_code == 201
    assert owner_password


async def test_five_wrong_codes_end_a_registration_whatever_the_resends(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        registration_id = await register(bench.http, form(EMAIL))
        [code] = await mailed_codes(run_slot, bench.key_ring, Home.RU)
        wrong = "000000" if code != "000000" else "111111"
        answers = [
            await bench.http.post(
                "/v1/auth/register/verify",
                json={"registration_id": str(registration_id), "code": wrong},
            )
            for _ in range(MAX_CODE_ATTEMPTS)
        ]
        await homes_execute(
            run_slot, "UPDATE pending_registrations SET last_sent_at = now() - interval '2 minutes'"
        )
        resent = await bench.http.post(
            "/v1/auth/register/resend", json={"registration_id": str(registration_id)}
        )
        new_code = (await mailed_codes(run_slot, bench.key_ring, Home.RU))[-1]
        final = await bench.http.post(
            "/v1/auth/register/verify",
            json={"registration_id": str(registration_id), "code": new_code},
        )

    codes = [answer.json()["error"]["code"] for answer in answers]
    assert codes == ["invalid_code"] * (MAX_CODE_ATTEMPTS - 1) + ["registration_locked"]
    assert resent.status_code == 202
    assert final.json()["error"]["code"] == "registration_locked"
    assert await rows(run_slot, Home.RU, "SELECT id FROM users") == []


async def homes_execute(run_slot: RunSlot, statement: str) -> None:
    """Run a statement in the Russian home as the migration role (a test's time travel)."""
    await run_slot.claimed.connections[Home.RU].execute(statement)


async def test_a_taken_address_gets_the_same_answer_and_its_owner_a_warning(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        first = await register(bench.http, form(EMAIL))
        [code] = await mailed_codes(run_slot, bench.key_ring, Home.RU)
        await bench.http.post(
            "/v1/auth/register/verify", json={"registration_id": str(first), "code": code}
        )
        again = await bench.http.post("/v1/auth/register", json=form(EMAIL, "DE"))
        decoy = UUID(again.json()["registration_id"])
        decoy_verify = await bench.http.post(
            "/v1/auth/register/verify", json={"registration_id": str(decoy), "code": "123456"}
        )

    assert again.status_code == 202
    assert set(again.json()) == {"registration_id", "resend_after_seconds"}
    assert decoy_verify.status_code == 400
    assert await rows(run_slot, Home.EU, "SELECT id FROM pending_registrations") == []
    warnings = await rows(
        run_slot,
        Home.RU,
        "SELECT recipient FROM email_messages WHERE template = 'identity.registration_attempt'",
    )
    assert warnings == [{"recipient": EMAIL}]


async def test_without_the_directory_registration_answers_503(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(
        homes.transactions, valkey, redis_cache, directory_transactions=eu_unreachable
    ) as bench:
        answer = await bench.http.post("/v1/auth/register", json=form(EMAIL))

    assert answer.status_code == 503
    assert answer.json()["error"]["code"] == "home_unavailable"
    assert await rows(run_slot, Home.RU, "SELECT id FROM pending_registrations") == []


async def test_a_resend_waits_a_minute_and_replaces_the_code(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        registration_id = await register(bench.http, form(EMAIL))
        too_soon = await bench.http.post(
            "/v1/auth/register/resend", json={"registration_id": str(registration_id)}
        )
        await homes_execute(
            run_slot, "UPDATE pending_registrations SET last_sent_at = now() - interval '2 minutes'"
        )
        resent = await bench.http.post(
            "/v1/auth/register/resend", json={"registration_id": str(registration_id)}
        )
        old_code, new_code = await mailed_codes(run_slot, bench.key_ring, Home.RU)
        with_old = await bench.http.post(
            "/v1/auth/register/verify",
            json={"registration_id": str(registration_id), "code": old_code},
        )
        with_new = await bench.http.post(
            "/v1/auth/register/verify",
            json={"registration_id": str(registration_id), "code": new_code},
        )

    assert too_soon.status_code == 429
    assert too_soon.json()["error"]["code"] == "resend_too_soon"
    assert "Retry-After" in too_soon.headers
    assert resent.status_code == 202
    assert (with_old.status_code, with_new.status_code) == (400, 201)
