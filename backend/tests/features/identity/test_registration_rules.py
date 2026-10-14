"""Registration refuses a broken form by its rule, and stops without Valkey (step 2)."""

import pytest
from redis.asyncio import Redis

from shosai.core.kernel.homes import Home
from shosai.core.kernel.ids import new_id
from shosai.features.identity.domain.registration import (
    CODE_DIGITS,
    RegistrationConsents,
    RegistrationProblem,
    code_hash,
    code_matches,
    new_code,
)
from tests.features.identity.registration_bench import form, registration_bench
from tests.harness.database_access import DatabaseAccess

EMAIL = "rules@example.com"


@pytest.mark.parametrize(
    ("change", "code"),
    [
        ({"email": "no-at-sign.example.com"}, "invalid_email"),
        ({"password": "short"}, "password_too_short"),
        ({"country": "XX1"}, None),
        ({"language": "xx"}, "unsupported_language"),
        ({"consents": {"personal_data": False}}, "personal_data_consent_required"),
        (
            {"consents": {"personal_data": True, "cross_border": False}},
            "cross_border_consent_required",
        ),
    ],
)
async def test_a_broken_form_is_refused_by_its_rule(
    homes: DatabaseAccess,
    valkey: Redis,
    redis_cache: Redis,
    change: dict[str, object],
    code: str | None,
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        answer = await bench.http.post("/v1/auth/register", json={**form(EMAIL), **change})

    assert answer.status_code == 422
    if code is not None:
        assert answer.json()["error"]["code"] == code


async def test_the_eu_home_needs_no_cross_border_consent(
    homes: DatabaseAccess, valkey: Redis, redis_cache: Redis
) -> None:
    body = {**form(EMAIL, "DE"), "consents": {"personal_data": True}}
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        answer = await bench.http.post("/v1/auth/register", json=body)

    assert answer.status_code == 202


async def test_without_valkey_registration_answers_503(
    homes: DatabaseAccess, redis_cache: Redis
) -> None:
    unreachable = Redis.from_url("redis://127.0.0.1:9/0", socket_connect_timeout=0.1)
    try:
        async with registration_bench(homes.transactions, unreachable, redis_cache) as bench:
            answer = await bench.http.post("/v1/auth/register", json=form(EMAIL))
    finally:
        await unreachable.aclose()

    assert answer.status_code == 503
    assert answer.json()["error"]["code"] == "registration_unavailable"


def test_a_code_is_six_digits_and_bound_to_its_registration() -> None:
    first, second = new_id(), new_id()
    code = new_code()

    assert len(code) == CODE_DIGITS
    assert code.isdigit()
    assert code_matches(first, code, code_hash(first, code))
    assert not code_matches(second, code, code_hash(first, code))
    assert not code_matches(first, "١٢٣٤٥٦", code_hash(first, code))


def test_consents_follow_the_home() -> None:
    russian = RegistrationConsents(personal_data=True, cross_border=False, marketing=False)
    nothing = RegistrationConsents(personal_data=False, cross_border=True, marketing=True)

    assert russian.problem(Home.RU) is RegistrationProblem.CROSS_BORDER_CONSENT_REQUIRED
    assert russian.problem(Home.EU) is None
    assert nothing.problem(Home.EU) is RegistrationProblem.PERSONAL_DATA_CONSENT_REQUIRED
