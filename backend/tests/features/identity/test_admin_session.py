"""The one admin's session and the EU audit log (identity step 12a, ADR 0049)."""

from datetime import UTC, datetime

import pytest
from prometheus_client import CollectorRegistry
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from shosai.core.events.subscriptions import ReceivedEvent
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.homes import Home
from shosai.core.kernel.ids import new_id
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.kv.metrics import KeyValueMetrics
from shosai.core.kv.rate_limits import RateLimiter
from shosai.features.identity.application.admin_access import AdminAccess
from shosai.features.identity.channels.subscriptions import audit_operator_action
from shosai.features.identity.contracts import ADMIN_COOKIE, OperatorActed, OperatorAction
from shosai.features.identity.infrastructure.admin_sessions import AdminSessions
from shosai.features.identity.infrastructure.password_hasher import PasswordHasher
from tests.composition.public_routes import route_snapshot
from tests.features.identity.admin_bench import ADMIN_USERNAME, sign_in_admin
from tests.features.identity.registration_bench import registration_bench
from tests.features.identity.test_profile import bearer
from tests.features.identity.test_sign_in import account, login
from tests.harness.connections import fetch_rows
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot

SESSION = "/v1/admin/session"
# Вход, выход и проверка сессии — единственные маршруты админки без её cookie.
OPEN_ROUTES = {f"POST {SESSION}", f"DELETE {SESSION}"}


async def test_every_admin_route_refuses_without_the_admin_session(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        await account(bench, run_slot)
        person = bearer((await login(bench))["access_token"])
        admin = [
            (
                method,
                path.replace("{user_id}", str(new_id())).replace("{transfer_id}", str(new_id())),
            )
            for method, _, path in (
                key.partition(" ") for key in route_snapshot(bench.app) if key not in OPEN_ROUTES
            )
            if path.startswith("/v1/admin/")
        ]
        forged = {"Cookie": f"{ADMIN_COOKIE}=bm9uY2U.bWFj"}
        answers = [
            await bench.http.request(method, path, headers=headers, json={})
            for method, path in admin
            for headers in (person, forged)
        ]

    assert len(admin) >= 6
    assert {answer.status_code for answer in answers} == {401}
    assert {answer.json()["error"]["code"] for answer in answers} == {"admin_sign_in_required"}


async def test_the_admin_signs_in_and_out_and_the_old_cookie_stops_working(
    homes: DatabaseAccess, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        wrong_password = await sign_in_admin(bench.http, "not the admin's password")
        wrong_name = await bench.http.post(
            SESSION, json={"username": "root", "password": "a long admin passphrase"}
        )
        signed_in = await sign_in_admin(bench.http)
        cookie = signed_in.cookies[ADMIN_COOKIE]
        checked = await bench.http.get(SESSION)
        signed_out = await bench.http.delete(SESSION)
        replayed = await bench.http.get(SESSION, headers={"Cookie": f"{ADMIN_COOKIE}={cookie}"})
        again = await bench.http.delete(SESSION)

    assert {answer.json()["error"]["code"] for answer in (wrong_password, wrong_name)} == {
        "invalid_credentials"
    }
    assert signed_in.status_code == 204
    flags = signed_in.headers["set-cookie"].lower()
    for flag in ("httponly", "samesite=strict", "path=/v1/admin", "secure", "max-age=28800"):
        assert flag in flags
    assert (checked.status_code, signed_out.status_code, again.status_code) == (204, 204, 204)
    assert (replayed.status_code, replayed.json()["error"]["code"]) == (
        401, "admin_sign_in_required",
    )  # fmt: skip


async def test_sign_in_attempts_are_limited_per_address(
    homes: DatabaseAccess, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        answers = [await sign_in_admin(bench.http, "a wrong guess") for _ in range(6)]
        right = await sign_in_admin(bench.http)

    assert [answer.status_code for answer in answers] == [401] * 5 + [429]
    assert right.status_code == 429


async def test_without_credentials_the_admin_panel_stays_closed(valkey: Redis) -> None:
    hasher = PasswordHasher(4, workers=1)
    limiter = RateLimiter(valkey, KeyValueMetrics(CollectorRegistry()))
    access = AdminAccess(None, hasher, AdminSessions(valkey, b"k" * 32), limiter)
    try:
        with pytest.raises(AppError) as raised:
            await access.sign_in(ADMIN_USERNAME, "a long admin passphrase", "127.0.0.1")
    finally:
        hasher.close()

    assert raised.value.code == "admin_sign_in_disabled"


async def test_an_action_leaves_one_audit_row_that_the_application_cannot_change(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    target = new_id()
    event = OperatorActed(
        target_user_id=target, target_home=Home.RU,
        action=OperatorAction.ACCOUNT_TRANSFER_REQUESTED,
    )  # fmt: skip
    received = ReceivedEvent(event, new_id(), 1, datetime.now(UTC), TenancyScope(Home.RU, target))
    eu = TenancyScope(Home.EU)
    for _ in range(2):
        async with homes.transactions.begin(eu) as session:
            await audit_operator_action(session, received)

    rows = await fetch_rows(
        run_slot.claimed.connections[Home.EU],
        "SELECT operator_id, action FROM operator_audit_events",
    )
    assert rows == [{"operator_id": None, "action": "account_transfer_requested"}]
    for statement in (
        "UPDATE operator_audit_events SET reason_code = 'changed'",
        "DELETE FROM operator_audit_events",
    ):
        with pytest.raises(ProgrammingError, match="permission denied"):
            async with homes.transactions.begin(eu) as session:
                await session.execute(text(statement))
