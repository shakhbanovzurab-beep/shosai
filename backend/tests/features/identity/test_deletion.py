"""Asking for deletion and cancelling it by signing in (ID-D5, step 7a)."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from redis.asyncio import Redis

from shosai.core.events.domain_event import DomainEvent
from shosai.core.events.subscriptions import ReceivedEvent
from shosai.core.kernel.homes import Home
from shosai.core.kernel.ids import new_id
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.identity.channels.subscriptions import hide_in_directory, show_in_directory
from shosai.features.identity.contracts import AccountDeletionCancelled, AccountDeletionScheduled
from tests.features.identity.registration_bench import RegistrationBench, registration_bench
from tests.features.identity.test_profile import bearer
from tests.features.identity.test_sign_in import EMAIL, account, login, refresh_with
from tests.harness.connections import fetch_rows
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot


async def ask(bench: RegistrationBench, token: object, email: str = EMAIL) -> tuple[int, object]:
    answer = await bench.http.post(
        "/v1/me/deletion", json={"confirm_email": email}, headers=bearer(token)
    )
    body = answer.json()
    return answer.status_code, body.get("error", {}).get("code") or body.get("erase_at")


async def events(run_slot: RunSlot) -> list[object]:
    rows = await fetch_rows(
        run_slot.claimed.connections[Home.RU],
        "SELECT event_type FROM outbox_messages ORDER BY occurred_at, id",
    )
    return [row["event_type"] for row in rows]


async def test_deletion_needs_the_address_again_and_a_fresh_sign_in(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        await account(bench, run_slot)
        token = (await login(bench))["access_token"]
        mismatch = await ask(bench, token, "someone@example.com")
        await run_slot.claimed.connections[Home.RU].execute(
            "UPDATE refresh_sessions SET created_at = now() - interval '16 minutes'"
        )
        stale = await ask(bench, token)

    assert mismatch == (400, "confirmation_mismatch")
    assert stale == (403, "reauthentication_required")


async def test_a_scheduled_account_has_no_session_and_hears_the_date(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        await account(bench, run_slot)
        signed_in = await login(bench)
        refresh_token = bench.http.cookies.get("meetassist_refresh") or ""
        csrf_token = bench.http.cookies.get("meetassist_csrf") or ""
        status, erase_at = await ask(bench, signed_in["access_token"], EMAIL.upper())
        cleared = bench.http.cookies.get("meetassist_refresh")
        me = await bench.http.get("/v1/me", headers=bearer(signed_in["access_token"]))
        refreshed = await refresh_with(bench, refresh_token, csrf_token)

    connection = run_slot.claimed.connections[Home.RU]
    [user] = await fetch_rows(connection, "SELECT state FROM users")
    [mail] = await fetch_rows(
        connection,
        "SELECT params FROM email_messages WHERE template = 'identity.deletion_scheduled'",
    )
    assert status == 202
    assert cleared is None
    assert (me.status_code, me.json()["detail"]) == (401, "Token revoked")
    assert refreshed[0] == 401
    assert user["state"] == "deletion_scheduled"
    assert mail["params"] == {"date": str(erase_at)[:10]}
    assert await events(run_slot) == [
        "identity.account.registered",
        "identity.account.deletion_scheduled",
        "identity.sessions.revoked",
    ]


async def test_a_sign_in_on_day_6_brings_everything_back_unchanged(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        await account(bench, run_slot)
        token = (await login(bench))["access_token"]
        await bench.http.patch("/v1/me", headers=bearer(token), json={"display_name": "Аня"})
        before = (await bench.http.get("/v1/me", headers=bearer(token))).json()
        await ask(bench, token)
        await run_slot.claimed.connections[Home.RU].execute(
            "UPDATE account_deletions SET requested_at = requested_at - interval '6 days', "
            "erase_at = erase_at - interval '6 days', run_at = run_at - interval '6 days'"
        )
        back = (await login(bench))["access_token"]
        after = (await bench.http.get("/v1/me", headers=bearer(back))).json()

    connection = run_slot.claimed.connections[Home.RU]
    [deletion] = await fetch_rows(connection, "SELECT state, cancelled_at FROM account_deletions")
    assert after == before
    assert deletion["state"] == "cancelled"
    assert deletion["cancelled_at"] is not None
    assert (await events(run_slot))[-1] == "identity.account.deletion_cancelled"


def received[E: DomainEvent](event: E, user_id: UUID, at: datetime) -> ReceivedEvent[E]:
    return ReceivedEvent(event, new_id(), 1, at, TenancyScope(Home.RU, user_id))


async def test_the_directory_follows_the_window_and_ignores_a_late_event(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        user_id = await account(bench, run_slot)
    now, eu = datetime.now(UTC), TenancyScope(Home.EU, user_id)
    scheduled = AccountDeletionScheduled(user_id=user_id, erase_at=now + timedelta(days=7))
    cancelled = AccountDeletionCancelled(user_id=user_id)

    async def state() -> object:
        [entry] = await fetch_rows(
            run_slot.claimed.connections[Home.EU], "SELECT state FROM directory_entries"
        )
        return entry["state"]

    async with homes.transactions.begin(eu) as session:
        await hide_in_directory(session, received(scheduled, user_id, now + timedelta(seconds=1)))
    hidden = await state()
    async with homes.transactions.begin(eu) as session:
        await show_in_directory(session, received(cancelled, user_id, now - timedelta(minutes=1)))
    late = await state()
    async with homes.transactions.begin(eu) as session:
        await show_in_directory(session, received(cancelled, user_id, now + timedelta(seconds=2)))

    assert (hidden, late, await state()) == ("deletion_scheduled", "deletion_scheduled", "active")
