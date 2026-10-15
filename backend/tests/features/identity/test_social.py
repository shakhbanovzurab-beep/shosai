"""Social sign-in through provider doubles: every path ends on the sign-in page (step 5)."""

from urllib.parse import parse_qs, urlsplit

from redis.asyncio import Redis

from shosai.core.kernel.homes import Home
from shosai.features.identity.domain.social import Provider
from tests.features.identity.registration_bench import (
    BenchOptions,
    RegistrationBench,
    registration_bench,
)
from tests.features.identity.social_doubles import ProviderDouble, identity
from tests.features.identity.test_sign_in import EMAIL, account
from tests.harness.connections import fetch_rows
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot

GOOGLE_NEW = identity(Provider.GOOGLE, "g-1", "new.person@example.com")
YANDEX_EXISTING = identity(Provider.YANDEX, "y-1", EMAIL)
VK_EXISTING = identity(Provider.VK, "v-1", EMAIL, verified=False)
DOUBLES = {
    Provider.GOOGLE: ProviderDouble(Provider.GOOGLE, {"new": GOOGLE_NEW}),
    Provider.YANDEX: ProviderDouble(Provider.YANDEX, {"existing": YANDEX_EXISTING}),
    Provider.VK: ProviderDouble(Provider.VK, {"existing": VK_EXISTING}),
}
WORLD = {"X-Country-Code": "DE"}
RUSSIA = {"X-Country-Code": "RU"}
CONSENTS = {"personal_data": True, "cross_border": False, "marketing": False}


def query_of(location: str) -> dict[str, str]:
    return {key: values[0] for key, values in parse_qs(urlsplit(location).query).items()}


async def come_back(bench: RegistrationBench, provider: Provider, code: str) -> dict[str, str]:
    """Start at the provider, come back with the code; the query of the sign-in page."""
    headers = WORLD if provider in {Provider.GOOGLE, Provider.GITHUB} else RUSSIA
    started = await bench.http.get(
        f"/v1/auth/social/{provider.value}/start", params={"next": "/app/notes"}, headers=headers
    )
    assert started.status_code == 302, started.text
    state = query_of(started.headers["location"])["state"]
    back = await bench.http.get(
        f"/v1/auth/social/{provider.value}/callback", params={"code": code, "state": state}
    )
    assert back.status_code == 302
    assert back.headers["location"].startswith("https://shosai.example/app/login?")
    return query_of(back.headers["location"])


def options() -> BenchOptions:
    return BenchOptions(providers=DOUBLES)


async def test_a_new_person_consents_then_signs_in_again_by_the_same_account(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache, options()) as bench:
        first = await come_back(bench, Provider.GOOGLE, "new")
        registered = await bench.http.post(
            "/v1/auth/social/register",
            json={"ticket": first["social_consent"], "country": "DE", "language": "de",
                  "consents": CONSENTS},
        )  # fmt: skip
        again = await come_back(bench, Provider.GOOGLE, "new")
        completed = await bench.http.post(
            "/v1/auth/social/complete", json={"ticket": again["social"]}
        )
        reused = await bench.http.post("/v1/auth/social/complete", json={"ticket": again["social"]})

    assert (first["social_provider"], first["next"]) == ("google", "/app/notes")
    assert registered.status_code == 200, registered.text
    assert completed.status_code == 200
    assert completed.json()["next"] == "/app/notes"
    assert (reused.status_code, reused.json()["error"]["code"]) == (401, "social_state_invalid")
    [user] = await fetch_rows(
        run_slot.claimed.connections[Home.EU],
        "SELECT email, password_hash, email_verified_at IS NOT NULL AS verified FROM users",
    )
    assert (user["email"], user["password_hash"], user["verified"]) == (
        "new.person@example.com", None, True,
    )  # fmt: skip
    links = await fetch_rows(
        run_slot.claimed.connections[Home.EU], "SELECT provider, subject FROM user_identities"
    )
    assert [(row["provider"], row["subject"]) for row in links] == [("google", "g-1")]


async def test_a_consent_ticket_opens_one_account_once(
    homes: DatabaseAccess, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache, options()) as bench:
        ticket = (await come_back(bench, Provider.GOOGLE, "new"))["social_consent"]
        body = {"ticket": ticket, "country": "DE", "language": "de", "consents": CONSENTS}
        first = await bench.http.post("/v1/auth/social/register", json=body)
        second = await bench.http.post("/v1/auth/social/register", json=body)

    assert first.status_code == 200
    assert (second.status_code, second.json()["error"]["code"]) == (400, "social_state_invalid")


async def test_a_proven_address_links_to_the_existing_account(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache, options()) as bench:
        user_id = await account(bench, run_slot)
        back = await come_back(bench, Provider.YANDEX, "existing")
        completed = await bench.http.post(
            "/v1/auth/social/complete", json={"ticket": back["social"]}
        )
        token = completed.json()["access_token"]
        me = await bench.http.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert me.json()["id"] == str(user_id)
    links = await fetch_rows(
        run_slot.claimed.connections[Home.RU], "SELECT provider, user_id FROM user_identities"
    )
    assert [(row["provider"], row["user_id"]) for row in links] == [("yandex", user_id)]


async def test_an_unproven_address_never_links_by_itself(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache, options()) as bench:
        await account(bench, run_slot)
        back = await come_back(bench, Provider.VK, "existing")

    assert back == {"social_error": "social_link_requires_sign_in"}
    assert (
        await fetch_rows(run_slot.claimed.connections[Home.RU], "SELECT id FROM user_identities")
        == []
    )


async def test_every_failure_is_a_redirect_with_its_reason(
    homes: DatabaseAccess, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache, options()) as bench:
        refused = await come_back(bench, Provider.GOOGLE, "unknown-code")
        crashed = await come_back(bench, Provider.GOOGLE, "explode")
        forged = await bench.http.get(
            "/v1/auth/social/google/callback", params={"code": "new", "state": "forged-state"}
        )
        cancelled = await bench.http.get(
            "/v1/auth/social/google/callback", params={"error": "denied"}
        )
        unknown = await bench.http.get("/v1/auth/social/myspace/callback", params={"code": "x"})
        hidden = await bench.http.get("/v1/auth/social/google/start", headers=RUSSIA)

    assert refused == {"social_error": "social_provider_failed"}
    assert crashed == {"social_error": "social_failed"}
    answers = [forged, cancelled, unknown, hidden]
    assert [answer.status_code for answer in answers] == [302] * 4
    assert [query_of(answer.headers["location"])["social_error"] for answer in answers] == [
        "social_state_invalid", "social_login_cancelled", "social_login_cancelled",
        "social_provider_disabled",
    ]  # fmt: skip


async def test_a_state_works_once(homes: DatabaseAccess, valkey: Redis, redis_cache: Redis) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache, options()) as bench:
        started = await bench.http.get("/v1/auth/social/google/start", headers=WORLD)
        state = query_of(started.headers["location"])["state"]
        params = {"code": "new", "state": state}
        first = await bench.http.get("/v1/auth/social/google/callback", params=params)
        replay = await bench.http.get("/v1/auth/social/google/callback", params=params)

    assert "social_consent" in query_of(first.headers["location"])
    assert query_of(replay.headers["location"]) == {"social_error": "social_state_invalid"}


async def test_the_two_sets_of_providers_are_never_shown_together(
    homes: DatabaseAccess, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache, options()) as bench:
        world = await bench.http.get("/v1/auth/social/providers", headers=WORLD)
        russia = await bench.http.get("/v1/auth/social/providers", headers=RUSSIA)
        # Страну edge не назвал: решает язык интерфейса, а не «по умолчанию Россия».
        unknown_english = await bench.http.get(
            "/v1/auth/social/providers", params={"language": "en"}
        )
        unknown_russian = await bench.http.get(
            "/v1/auth/social/providers", params={"language": "ru"}
        )
        russian_reader = await bench.http.get(
            "/v1/auth/social/providers", params={"language": "ru"}, headers=WORLD
        )
        page = await bench.http.get("/v1/auth/social/yandex/token-page")

    assert world.json()["providers"] == ["google"]
    assert russia.json()["providers"] == ["yandex", "vk"]
    assert russian_reader.json()["providers"] == ["yandex", "vk"]
    assert unknown_english.json()["providers"] == ["google"]
    assert unknown_russian.json()["providers"] == ["yandex", "vk"]
    assert page.text.count("<script") == 2
    assert "frame-ancestors 'none'" in page.headers["content-security-policy"]
