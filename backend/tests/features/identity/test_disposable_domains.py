"""No new account at a disposable mail service, on any way in (step 15; BL-D3, ADR 0054)."""

import pytest
from redis.asyncio import Redis

from shosai.core.kernel.homes import Home
from shosai.features.identity.domain import emails
from shosai.features.identity.domain.emails import is_disposable, normalize_email
from shosai.features.identity.domain.social import Provider
from tests.features.identity.registration_bench import BenchOptions, form, registration_bench
from tests.features.identity.social_doubles import ProviderDouble, identity
from tests.features.identity.test_email_sign_in import WORLD, codes, start, verify
from tests.features.identity.test_sign_in import account
from tests.features.identity.test_social import CONSENTS, come_back
from tests.harness.connections import fetch_rows
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot

THROWAWAY = "someone@yopmail.com"
REFUSED = (422, "email_domain_not_allowed")


@pytest.mark.parametrize(
    ("address", "disposable"),
    [
        ("a@mailinator.com", True),
        ("a@MAILINATOR.com", True),
        ("a@inbox.mailinator.com", True),
        ("a@guerrillamail.de", True),
        ("a@example.com", False),
        ("a@notmailinator.com", False),
        ("a@mailinator.company", False),
        ("a@yandex.ru", False),
    ],
)
def test_a_disposable_domain_and_its_subdomains_are_recognised(
    address: str, *, disposable: bool
) -> None:
    assert is_disposable(normalize_email(address)) is disposable


async def test_registration_with_a_password_refuses_a_disposable_address(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        refused = await bench.http.post("/v1/auth/register", json=form(THROWAWAY))

    assert (refused.status_code, refused.json()["error"]["code"]) == REFUSED
    assert (
        await fetch_rows(
            run_slot.claimed.connections[Home.RU], "SELECT 1 FROM pending_registrations"
        )
        == []
    )


async def test_a_code_never_opens_a_new_account_at_a_disposable_address(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        # Начало не отказывает: иначе ответ выдал бы, есть ли аккаунт на этом адресе.
        challenge = await start(bench.http, THROWAWAY, WORLD)
        [code] = await codes(run_slot, bench.key_ring, Home.EU)
        refused = await verify(bench.http, challenge, code)

    assert (refused.status_code, refused.json()["error"]["code"]) == REFUSED


async def test_an_account_registered_before_signs_in_by_the_code_as_usual(
    homes: DatabaseAccess,
    run_slot: RunSlot,
    valkey: Redis,
    redis_cache: Redis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        # Аккаунт появился до правила: на время регистрации список пуст.
        with monkeypatch.context() as patched:
            patched.setattr(emails, "DISPOSABLE_MAIL_DOMAINS", frozenset())
            await account(bench, run_slot, Home.EU, email=THROWAWAY)
        challenge = await start(bench.http, THROWAWAY, WORLD)
        signed_in = await verify(
            bench.http, challenge, (await codes(run_slot, bench.key_ring, Home.EU))[-1]
        )

    assert signed_in.status_code == 200, signed_in.text
    assert signed_in.json()["session"]["access_token"]


async def test_a_provider_s_disposable_address_opens_no_account(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    double = ProviderDouble(
        Provider.GOOGLE, {"throwaway": identity(Provider.GOOGLE, "g-9", THROWAWAY)}
    )
    options = BenchOptions(providers={Provider.GOOGLE: double})
    async with registration_bench(homes.transactions, valkey, redis_cache, options) as bench:
        back = await come_back(bench, Provider.GOOGLE, "throwaway")
        refused = await bench.http.post(
            "/v1/auth/social/register",
            json={
                "ticket": back["social_consent"],
                "country": "DE",
                "language": "de",
                "consents": CONSENTS,
            },
        )

    assert (refused.status_code, refused.json()["error"]["code"]) == REFUSED
    assert await fetch_rows(run_slot.claimed.connections[Home.EU], "SELECT 1 FROM users") == []
