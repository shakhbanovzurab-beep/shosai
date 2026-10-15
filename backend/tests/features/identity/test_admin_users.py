"""The admin's search, the card and the account actions (identity steps 8b and 12a, ADR 0049)."""

from datetime import UTC, datetime
from uuid import UUID

import httpx
from redis.asyncio import Redis

from shosai.core.events.subscriptions import ReceivedEvent
from shosai.core.kernel.homes import Home
from shosai.core.kernel.ids import new_id
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.identity.channels.subscriptions import audit_operator_action
from shosai.features.identity.contracts import OperatorActed, OperatorAction
from tests.features.identity.admin_bench import sign_in_admin
from tests.features.identity.registration_bench import RegistrationBench, registration_bench
from tests.features.identity.test_deletion import events
from tests.features.identity.test_profile import bearer
from tests.features.identity.test_sign_in import PASSWORD, account
from tests.harness.connections import fetch_rows
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot

RUSSIAN = "ivan.petrov@example.com"
EUROPEAN = "ivan.sidorov@example.com"


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
        await sign_in_admin(bench.http)

        async def search(**params: str | int | None) -> httpx.Response:
            return await bench.http.get("/v1/admin/users", params=params)

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


async def test_block_and_unblock_end_sessions_at_once_and_leave_one_audit_event_each(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        target = await account(bench, run_slot, email=RUSSIAN)
        await sign_in_admin(bench.http)
        live = bearer((await sign_in(bench, RUSSIAN)).json()["access_token"])
        reason = {"reason_code": "abuse"}

        async def act(action: str) -> httpx.Response:
            return await bench.http.post(f"/v1/admin/users/{target}/{action}", json=reason)

        blocked = await act("block")
        refused_live = await bench.http.get("/v1/auth/me", headers=live)
        refused_sign_in = await sign_in(bench, RUSSIAN)
        again = await act("block")
        unblocked = await act("unblock")
        back = await sign_in(bench, RUSSIAN)
        ban = await bench.http.post(f"/v1/admin/users/{target}/ban", json=reason)
        card = (await bench.http.get(f"/v1/admin/users/{target}")).json()

    assert blocked.json()["user"]["state"] == "frozen"
    assert (refused_live.status_code, refused_live.json()["detail"]) == (403, "account_frozen")
    assert refused_sign_in.json()["detail"] == "account_frozen"
    assert (again.status_code, back.status_code) == (200, 200)
    assert unblocked.json()["user"]["state"] == "active"
    assert ban.status_code in {404, 405}
    assert "operator_roles" not in card
    assert len(card["sessions"]) == 1
    assert card["spend"] == {"today_usd": "0", "week_usd": "0", "month_usd": "0"}
    names = await events(run_slot)
    assert names.count("identity.operator.acted") == 2
    assert names.count("identity.account.blocked") == 1
    assert names.count("identity.account.unblocked") == 1


async def test_an_account_banned_before_stays_closed(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        target = await account(bench, run_slot, email=RUSSIAN)
        await run_slot.claimed.connections[Home.RU].execute(
            "UPDATE users SET state = 'banned' WHERE id = %s", (target,)
        )
        await sign_in_admin(bench.http)
        unblocked = await bench.http.post(
            f"/v1/admin/users/{target}/unblock", json={"reason_code": "appeal"}
        )

    assert (unblocked.status_code, unblocked.json()["error"]["code"]) == (
        409, "account_state_conflict",
    )  # fmt: skip


async def test_the_directory_follows_a_block_and_the_audit_names_no_operator(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        target = await account(bench, run_slot)
    event = OperatorActed(
        target_user_id=target, target_home=Home.RU, action=OperatorAction.ACCOUNT_BLOCKED,
        reason_code="abuse",
    )  # fmt: skip
    received = ReceivedEvent(event, new_id(), 1, datetime.now(UTC), TenancyScope(Home.RU, target))
    async with homes.transactions.begin(TenancyScope(Home.EU)) as session:
        await audit_operator_action(session, received)

    eu = run_slot.claimed.connections[Home.EU]
    [entry] = await fetch_rows(eu, "SELECT state FROM directory_entries")
    [audit] = await fetch_rows(eu, "SELECT operator_id FROM operator_audit_events")
    assert (entry["state"], audit["operator_id"]) == ("frozen", None)
