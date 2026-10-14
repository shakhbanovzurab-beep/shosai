"""Support's search, the card and the account actions (identity step 8b, SM-12)."""

from datetime import UTC, datetime
from uuid import UUID

import httpx
from redis.asyncio import Redis

from shosai.core.events.subscriptions import ReceivedEvent
from shosai.core.kernel.homes import Home
from shosai.core.kernel.ids import new_id
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.identity.channels.subscriptions import audit_operator_action
from shosai.features.identity.contracts import OperatorActed, OperatorAction, OperatorRole
from tests.features.identity.registration_bench import RegistrationBench, registration_bench
from tests.features.identity.test_deletion import events
from tests.features.identity.test_operators import owner
from tests.features.identity.test_profile import bearer
from tests.features.identity.test_sign_in import PASSWORD, account, login
from tests.harness.connections import fetch_rows
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot

RUSSIAN = "ivan.petrov@example.com"
EUROPEAN = "ivan.sidorov@example.com"
SUPPORT = "support@example.com"


async def named(run_slot: RunSlot, home: Home, user_id: UUID, name: str) -> None:
    await run_slot.claimed.connections[home].execute(
        "UPDATE users SET full_name = %s WHERE id = %s", (name, user_id)
    )


async def sign_in(bench: RegistrationBench, email: str) -> httpx.Response:
    return await bench.http.post("/v1/auth/login", json={"email": email, "password": PASSWORD})


async def test_search_by_email_reaches_its_home_and_by_name_merges_both(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        russian = await account(bench, run_slot, email=RUSSIAN)
        european = await account(bench, run_slot, Home.EU, email=EUROPEAN)
        await named(run_slot, Home.RU, russian, "Ivan Petrov")
        await named(run_slot, Home.EU, european, "Ivan Sidorov")
        await account(bench, run_slot)
        await owner(bench)
        headers = bearer((await login(bench))["access_token"])

        async def search(**params: str | int | None) -> httpx.Response:
            return await bench.http.get("/v1/admin/users", params=params, headers=headers)

        by_email = (await search(email=EUROPEAN.upper())).json()
        first = (await search(name="IVAN", limit=1)).json()
        second = (await search(name="ivan", limit=1, cursor=first["next_cursor"])).json()
        unknown = (await search(email="nobody@example.com")).json()
        wildcard = (await search(name="%_")).json()
        refused = [await search(), await search(email=RUSSIAN, name="ivan")]

    assert [(item["id"], item["home"]) for item in by_email["items"]] == [(str(european), "eu")]
    assert [item["id"] for item in first["items"]] == [str(european)]
    assert [item["id"] for item in second["items"]] == [str(russian)]
    assert second["next_cursor"] is None
    assert (unknown["items"], wildcard["items"]) == ([], [])
    assert {answer.json()["error"]["code"] for answer in refused} == {"search_needs_email_or_name"}


async def test_block_unblock_and_ban_end_sessions_at_once_and_leave_one_audit_event_each(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        target = await account(bench, run_slot, email=RUSSIAN)
        me = await account(bench, run_slot)
        await owner(bench)
        headers = bearer((await login(bench))["access_token"])
        live = bearer((await sign_in(bench, RUSSIAN)).json()["access_token"])
        reason = {"reason_code": "abuse"}

        async def act(action: str, user_id: UUID = target) -> httpx.Response:
            path = f"/v1/admin/users/{user_id}/{action}"
            return await bench.http.post(path, json=reason, headers=headers)

        blocked = await act("block")
        refused_live = await bench.http.get("/v1/auth/me", headers=live)
        refused_sign_in = await sign_in(bench, RUSSIAN)
        again = await act("block")
        unblocked = await act("unblock")
        back = await sign_in(bench, RUSSIAN)
        banned = await act("ban")
        stays_banned = await act("unblock")
        banned_sign_in = await sign_in(bench, RUSSIAN)
        myself = await act("block", me)
        card = (await bench.http.get(f"/v1/admin/users/{target}", headers=headers)).json()

    assert blocked.json()["user"]["state"] == "frozen"
    assert (refused_live.status_code, refused_live.json()["detail"]) == (403, "account_frozen")
    assert refused_sign_in.json()["detail"] == "account_frozen"
    assert (again.status_code, back.status_code) == (200, 200)
    assert unblocked.json()["user"]["state"] == "active"
    assert banned.json()["user"]["state"] == "banned"
    assert banned_sign_in.json()["detail"] == "account_banned"
    assert (stays_banned.status_code, stays_banned.json()["error"]["code"]) == (
        409, "account_state_conflict",
    )  # fmt: skip
    assert (myself.status_code, myself.json()["error"]["code"]) == (409, "self_action")
    assert card["sessions"] == []
    assert card["spend"] == {"today_usd": "0", "week_usd": "0", "month_usd": "0"}
    names = await events(run_slot)
    assert names.count("identity.operator.acted") == 4
    assert names.count("identity.account.blocked") == 2
    assert names.count("identity.account.unblocked") == 1


async def test_only_an_owner_acts_on_an_operator_and_read_only_cannot_act(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        support = await account(bench, run_slot, email=SUPPORT)
        me = await account(bench, run_slot)
        await owner(bench)
        await bench.operators.set_roles(None, support, frozenset({OperatorRole.SUPPORT}))
        token = (await sign_in(bench, SUPPORT)).json()["access_token"]
        protected = await bench.http.post(
            f"/v1/admin/users/{me}/block", json={"reason_code": "test"}, headers=bearer(token)
        )
        await bench.operators.set_roles(None, support, frozenset({OperatorRole.READ_ONLY}))
        read = await bench.http.get(f"/v1/admin/users/{me}", headers=bearer(token))
        act = await bench.http.post(
            f"/v1/admin/users/{me}/block", json={"reason_code": "test"}, headers=bearer(token)
        )

    assert (protected.status_code, protected.json()["error"]["code"]) == (
        403, "operator_protected",
    )  # fmt: skip
    assert read.json()["operator_roles"] == ["owner"]
    assert (act.status_code, act.json()["error"]["code"]) == (403, "operator_role_required")


async def test_the_directory_follows_a_ban(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        target = await account(bench, run_slot)
    event = OperatorActed(
        operator_id=new_id(), target_user_id=target, target_home=Home.RU,
        action=OperatorAction.ACCOUNT_BANNED, reason_code="abuse",
    )  # fmt: skip
    received = ReceivedEvent(event, new_id(), 1, datetime.now(UTC), TenancyScope(Home.RU, target))
    async with homes.transactions.begin(TenancyScope(Home.EU)) as session:
        await audit_operator_action(session, received)

    [entry] = await fetch_rows(
        run_slot.claimed.connections[Home.EU], "SELECT state FROM directory_entries"
    )
    assert entry["state"] == "banned"
