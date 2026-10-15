"""The shipped desktop clients' sign-in, replayed against the composed API app (identity step 13).

Each test sends the requests of macOS and Windows 1.4.5 in their order, with their headers
and bodies (`contracts/draft/consumers.json` names the call sites), to the app the `api`
role really builds, and decodes every answer the way the clients do (`native_clients`).
The browser sign-in is replayed up to the code: the cabinet redirects to `shosai://auth`,
which the shipped builds do not register yet (ADR 0045, ID-D10), so the replay hands the
code to the app as its callback would.
"""

import hashlib
from base64 import urlsafe_b64encode
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Final

import httpx
from fastapi import FastAPI
from redis.asyncio import Redis
from shosai_contracts import (
    Candidate,
    CompatClass,
    Scope,
    check,
    load_baseline,
    parse_routes,
    render_text,
)
from shosai_contracts.jsonvalue import Json

from shosai.composition.features import FEATURES
from tests.composition.native_clients import (
    decode_auth_user,
    decode_desktop_tokens,
    decode_token_response,
)
from tests.composition.public_routes import route_snapshot
from tests.composition.test_public_routes import SNAPSHOT, compose
from tests.features.identity.passwordless_bench import DIRECTORY_KEY, SIGNING_KEYS
from tests.features.identity.registration_bench import registration_bench
from tests.features.identity.test_sign_in import EMAIL, PASSWORD, account
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot
from tests.harness.settings import HarnessSettings

# Ключи стенда identity: аккаунт, созданный стендом, виден собранному приложению.
KEYS: Final = {
    "IDENTITY_DIRECTORY_HMAC_KEY": DIRECTORY_KEY.decode(),
    "IDENTITY_TOKEN_KEYS": f"{SIGNING_KEYS[0].key_id}:{SIGNING_KEYS[0].secret.get_secret_value()}",
}
# Адрес, который зашит в выпущенные клиенты.
CLIENT_BASE: Final = "https://whisperer.one"
DESKTOP: Final = {"X-Client-Kind": "desktop"}
# Сериализаторы клиентов шлют null явно: `captcha_token` всегда есть в теле.
LOGIN: Final = {"email": EMAIL, "password": PASSWORD, "captcha_token": None}
# Маршруты S01 (identity в нарезке черновика), которыми пользуются выпущенные клиенты.
IDENTITY_NATIVE: Final = Scope(
    slices=frozenset({"S01"}), classes=frozenset({CompatClass.NATIVE}), served_only=True
)
VERIFIER: Final = "dGhlLXZlcmlmaWVyLW9mLXRoZS1tYWNvcy1jbGllbnQtNDM"


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def connection(app: FastAPI) -> httpx.AsyncClient:
    """One client's cookie jar and connection, as an app or a browser keeps them."""
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=CLIENT_BASE)


@asynccontextmanager
async def composed_api(
    run_slot: RunSlot,
    harness_settings: HarnessSettings,
    services: tuple[DatabaseAccess, Redis, Redis],
) -> AsyncIterator[FastAPI]:
    """The api app with one confirmed account of `EMAIL` in the Russian home."""
    homes, valkey, cache = services
    async with registration_bench(homes.transactions, valkey, cache) as bench:
        await account(bench, run_slot)
    async with compose(run_slot, harness_settings, FEATURES, KEYS) as apps:
        yield apps["api"]


async def desktop_code(app: FastAPI, challenge: str | None) -> str:
    """The code the cabinet's connect page gets for the signed-in browser."""
    async with connection(app) as browser:
        signed_in = await browser.post("/v1/auth/login", json=LOGIN)
        token = decode_token_response(signed_in.json())
        body = (
            None
            if challenge is None
            else {"code_challenge": challenge, "code_challenge_method": "S256"}
        )
        issued = await browser.post("/v1/auth/desktop/code", json=body, headers=bearer(token))
    assert issued.status_code == 200, issued.text
    return str(issued.json()["code"])


async def test_password_sign_in_with_cookie_refresh_as_both_clients_send_it(
    run_slot: RunSlot,
    harness_settings: HarnessSettings,
    homes: DatabaseAccess,
    valkey: Redis,
    redis_cache: Redis,
) -> None:
    async with (
        composed_api(run_slot, harness_settings, (homes, valkey, redis_cache)) as app,
        connection(app) as client,
    ):
        wrong = await client.post(
            "/v1/auth/login", json={**LOGIN, "password": "not the password"}, headers=DESKTOP
        )
        signed_in = await client.post("/v1/auth/login", json=LOGIN, headers=DESKTOP)
        access = decode_token_response(signed_in.json())
        profile = await client.get("/v1/auth/me", headers=bearer(access))
        # Восстановление при запуске и плановое продление: cookie и X-CSRF-Token из cookie.
        csrf = {"X-CSRF-Token": client.cookies.get("meetassist_csrf") or ""}
        refreshed = await client.post("/v1/auth/refresh", headers=csrf)
        again = await client.get(
            "/v1/auth/me", headers=bearer(decode_token_response(refreshed.json()))
        )
        signed_out = await client.post("/v1/auth/logout")
        after = await client.post("/v1/auth/refresh", headers=csrf)

    # Клиенты различают отказ по статусу: 401 на /auth/login — «неверная почта или пароль».
    assert wrong.status_code == 401
    assert isinstance(wrong.json()["detail"], str)
    assert signed_in.status_code == 200
    assert decode_auth_user(profile.json()) == EMAIL
    assert refreshed.status_code == 200
    assert decode_auth_user(again.json()) == EMAIL
    # Клиенты не читают ответ выхода; важно, что сервер его принял и сессия кончилась.
    assert signed_out.status_code < 500
    assert after.status_code == 401


async def test_browser_sign_in_of_macos_with_pkce(
    run_slot: RunSlot,
    harness_settings: HarnessSettings,
    homes: DatabaseAccess,
    valkey: Redis,
    redis_cache: Redis,
) -> None:
    challenge = urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest()).rstrip(b"=").decode()
    async with composed_api(run_slot, harness_settings, (homes, valkey, redis_cache)) as app:
        code = await desktop_code(app, challenge)
        async with connection(app) as client:
            exchanged = await client.post(
                "/v1/auth/desktop/exchange", json={"code": code, "code_verifier": VERIFIER}
            )
            access, refresh = decode_desktop_tokens(exchanged.json())
            profile = await client.get("/v1/auth/me", headers=bearer(access))
            rotated = await client.post("/v1/auth/desktop/refresh", json={"refresh_token": refresh})
            new_access, new_refresh = decode_desktop_tokens(rotated.json())
            again = await client.get("/v1/auth/me", headers=bearer(new_access))

    assert exchanged.status_code == 200
    assert decode_auth_user(profile.json()) == EMAIL
    assert new_refresh != refresh
    assert decode_auth_user(again.json()) == EMAIL


async def test_browser_sign_in_of_windows_without_pkce(
    run_slot: RunSlot,
    harness_settings: HarnessSettings,
    homes: DatabaseAccess,
    valkey: Redis,
    redis_cache: Redis,
) -> None:
    async with composed_api(run_slot, harness_settings, (homes, valkey, redis_cache)) as app:
        code = await desktop_code(app, None)
        async with connection(app) as client:
            exchanged = await client.post("/v1/auth/desktop/exchange", json={"code": code})
            access, refresh = decode_desktop_tokens(exchanged.json())
            profile = await client.get("/v1/auth/me", headers=bearer(access))
            rotated = await client.post("/v1/auth/desktop/refresh", json={"refresh_token": refresh})
            again = await client.get(
                "/v1/auth/me", headers=bearer(decode_desktop_tokens(rotated.json())[0])
            )
            signed_out = await client.post("/v1/auth/logout")

    assert decode_auth_user(profile.json()) == EMAIL
    assert rotated.status_code == 200
    assert decode_auth_user(again.json()) == EMAIL
    assert signed_out.status_code < 500


async def test_the_gate_serves_every_native_identity_route(
    run_slot: RunSlot, harness_settings: HarnessSettings
) -> None:
    async with compose(run_slot, harness_settings, FEATURES) as apps:
        routes: list[Json] = [route for app in apps.values() for route in route_snapshot(app)]
        candidate = Candidate(
            openapi=apps["api"].openapi(), routes=parse_routes(routes, SNAPSHOT.name)
        )
        report = check(load_baseline(), candidate, IDENTITY_NATIVE)

    assert report.unserved == ()
    assert report.is_compatible, render_text(report, IDENTITY_NATIVE)
