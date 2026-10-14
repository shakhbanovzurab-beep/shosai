"""The authenticator: draft tokens, Valkey outages and the captcha after failures (step 3a)."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from prometheus_client import CollectorRegistry
from pydantic import SecretStr
from redis.asyncio import Redis

from shosai.core.cache.metrics import CacheMetrics
from shosai.core.cache.redis_cache import RedisCache
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.homes import Home
from shosai.core.kernel.ids import new_id
from shosai.features.identity.application.authentication import TokenAuthenticator
from shosai.features.identity.domain.tokens import AccessClaims
from shosai.features.identity.infrastructure.account_markers import AccountMarkers
from shosai.features.identity.infrastructure.directory import Directory
from shosai.features.identity.infrastructure.token_codec import TokenCodec
from shosai.features.identity.settings import TokenKey
from tests.features.identity.registration_bench import (
    BenchOptions,
    RegistrationBench,
    form,
    mailed_codes,
    registration_bench,
)
from tests.features.identity.test_sign_in import EMAIL, PASSWORD, account
from tests.harness.connections import fetch_rows
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot

DRAFT_SECRET = "draft-secret-of-the-identity-tests-32b"
KEYS = (
    TokenKey("k1", SecretStr("signing-key-of-the-identity-tests-32b")),
    TokenKey("d", SecretStr(DRAFT_SECRET)),
)


def authenticator(homes: DatabaseAccess, cache: Redis, valkey: Redis) -> TokenAuthenticator:
    directory = Directory(homes.transactions, RedisCache(cache, CacheMetrics(CollectorRegistry())))
    return TokenAuthenticator(TokenCodec(KEYS), directory, AccountMarkers(valkey))


def access_token(home: Home | None, issued: timedelta = timedelta(0)) -> str:
    now = datetime.now(UTC) - issued
    claims = AccessClaims(new_id(), home, 0, now, now + timedelta(minutes=30))
    return TokenCodec(KEYS).encode_access(claims)


async def test_without_valkey_a_request_passes_on_its_signature(
    homes: DatabaseAccess, redis_cache: Redis
) -> None:
    silent = Redis.from_url("redis://127.0.0.1:9/0", socket_connect_timeout=0.05)
    try:
        principal = await authenticator(homes, redis_cache, silent).principal(access_token(Home.EU))
    finally:
        await silent.aclose()

    assert principal.home is Home.EU


async def test_a_draft_token_without_home_finds_it_in_the_directory(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        user_id = await account(bench, run_slot)
    now = int(datetime.now(UTC).timestamp())
    payload = {"sub": str(user_id), "typ": "access", "tv": 0, "iat": now, "exp": now + 600}
    draft = jwt.encode(payload, DRAFT_SECRET, algorithm="HS256")

    principal = await authenticator(homes, redis_cache, valkey).principal(draft)

    assert (principal.user_id, principal.home) == (user_id, Home.RU)


@pytest.mark.parametrize(
    ("token", "detail"),
    [
        (access_token(Home.RU, issued=timedelta(hours=1)), "Token expired"),
        ("not-a-token", "Invalid token"),
        (access_token(None), "User not found"),
    ],
)
async def test_a_bad_token_answers_the_drafts_detail(
    homes: DatabaseAccess, valkey: Redis, redis_cache: Redis, token: str, detail: str
) -> None:
    with pytest.raises(AppError) as raised:
        await authenticator(homes, redis_cache, valkey).principal(token)

    assert (raised.value.status, raised.value.detail) == (401, detail)


class OnlyOk:
    """A captcha that passes the token `ok` alone."""

    async def passed(self, token: str | None, remote_address: str) -> bool:
        del remote_address
        return token == "ok"


async def test_three_failures_bring_the_captcha_for_every_client(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(
        homes.transactions, valkey, redis_cache, BenchOptions(captcha=OnlyOk())
    ) as bench:
        registration = {**form(EMAIL), "captcha_token": "ok"}
        await bench.http.post("/v1/auth/register", json=registration)
        await account_from_pending(bench, run_slot)
        wrong = {"email": EMAIL, "password": "nope"}
        failures = [await bench.http.post("/v1/auth/login", json=wrong) for _ in range(3)]
        desktop = await bench.http.post(
            "/v1/auth/login",
            json={"email": EMAIL, "password": PASSWORD},
            headers={"X-Client-Kind": "desktop"},
        )
        solved = await bench.http.post(
            "/v1/auth/login", json={"email": EMAIL, "password": PASSWORD, "captcha_token": "ok"}
        )

    assert [answer.status_code for answer in failures] == [401, 401, 401]
    assert (desktop.status_code, desktop.json()["detail"]) == (400, "captcha_failed")
    assert solved.status_code == 200


async def account_from_pending(bench: RegistrationBench, run_slot: RunSlot) -> None:
    """Confirm the registration the test started (its code is the last one mailed)."""
    [pending] = await fetch_rows(
        run_slot.claimed.connections[Home.RU], "SELECT id FROM pending_registrations"
    )
    code = (await mailed_codes(run_slot, bench.key_ring, Home.RU))[-1]
    answer = await bench.http.post(
        "/v1/auth/register/verify", json={"registration_id": str(pending["id"]), "code": code}
    )
    assert answer.status_code == 201
    bench.http.cookies.clear()
