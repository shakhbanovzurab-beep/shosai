"""Sign-in through VK ID OneTap: the flow opens on the server, the widget hands back the code."""

import hashlib
from base64 import urlsafe_b64encode

import httpx
from redis.asyncio import Redis

from shosai.features.identity.domain.social import Provider
from tests.features.identity.registration_bench import BenchOptions, registration_bench
from tests.features.identity.social_doubles import WIDGET_REDIRECT, ProviderDouble, identity
from tests.harness.database_access import DatabaseAccess

VK = ProviderDouble(Provider.VK, {"new": identity(Provider.VK, "v-2", "new.vk@example.com")})
GOOGLE = ProviderDouble(Provider.GOOGLE, {})


def refusals(*answers: httpx.Response) -> list[tuple[int, str]]:
    return [(answer.status_code, answer.json()["error"]["code"]) for answer in answers]


async def widget_start(http: httpx.AsyncClient, provider: str, language: str) -> httpx.Response:
    return await http.post(
        f"/v1/auth/social/{provider}/widget-start",
        json={"next": "/app/notes", "language": language},
    )


async def test_onetap_opens_a_flow_and_its_code_signs_a_new_person_in_once(
    homes: DatabaseAccess, valkey: Redis, redis_cache: Redis
) -> None:
    options = BenchOptions(providers={Provider.VK: VK, Provider.GOOGLE: GOOGLE})
    async with registration_bench(homes.transactions, valkey, redis_cache, options) as bench:
        started = await widget_start(bench.http, "vk", "ru")
        flow = started.json()
        code = {"code": "new", "state": flow["state"], "device_id": "device-1"}
        arrived = await bench.http.post("/v1/auth/social/vk/widget-code", json=code)
        replayed = await bench.http.post("/v1/auth/social/vk/widget-code", json=code)
        forged = await bench.http.post(
            "/v1/auth/social/vk/widget-code", json={**code, "state": "forged-state"}
        )

    assert started.status_code == 200, started.text
    assert flow["redirect_url"] == WIDGET_REDIRECT
    # Сервер хранит verifier, виджет получает только его хеш (S256).
    challenge = urlsafe_b64encode(hashlib.sha256(VK.verifiers[0].encode()).digest())
    assert flow["code_challenge"] == challenge.rstrip(b"=").decode()
    assert VK.device_ids[0] == "device-1"
    assert arrived.status_code == 200, arrived.text
    assert arrived.json()["social_consent"]
    assert arrived.json()["next"] == "/app/notes"
    assert refusals(replayed, forged) == [(401, "social_state_invalid")] * 2


async def test_onetap_is_only_for_vk_and_only_where_vk_is_shown(
    homes: DatabaseAccess, valkey: Redis, redis_cache: Redis
) -> None:
    options = BenchOptions(providers={Provider.VK: VK, Provider.GOOGLE: GOOGLE})
    async with registration_bench(homes.transactions, valkey, redis_cache, options) as bench:
        english = await widget_start(bench.http, "vk", "en")
        google = await widget_start(bench.http, "google", "en")

    assert refusals(english, google) == [(409, "social_provider_disabled")] * 2
