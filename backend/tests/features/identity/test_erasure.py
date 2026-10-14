"""The erasure saga after the window: nothing of the person remains (ID-D5, step 7a)."""

from collections.abc import AsyncIterator, Mapping
from uuid import UUID

import pytest
from prometheus_client import CollectorRegistry
from psycopg import sql
from redis.asyncio import Redis

from shosai.core.account_data.handlers import (
    ACCOUNT_DATA_HANDLERS,
    AccountDataHandler,
    AccountRef,
    ExportFile,
)
from shosai.core.email.account_data import CoreAccountData
from shosai.core.events.catalog import EventTypes
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.homes import Home
from shosai.core.ports.directory import PortDirectory
from shosai.core.storage.port import ObjectStorage
from shosai.features.identity.application.account_data import IdentityAccountData
from shosai.features.identity.application.erasure import Erasure
from shosai.features.identity.contracts import IDENTITY_EVENTS
from shosai.features.identity.infrastructure.deletion_metrics import DeletionMetrics
from tests.core.storage.adapters import slot_storage
from tests.features.identity.registration_bench import (
    BenchOptions,
    RegistrationBench,
    registration_bench,
)
from tests.features.identity.test_deletion import ask, events
from tests.features.identity.test_profile import bearer, png
from tests.features.identity.test_sign_in import EMAIL, PASSWORD, account, login
from tests.harness.connections import fetch_rows
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot
from tests.harness.shared_services import SlotBucket

ERASED_TABLES = (
    "user_consents", "refresh_sessions", "login_events", "password_reset_tokens",
    "user_identities", "account_deletions", "email_messages", "email_suppressions",
)  # fmt: skip


class Flaky:
    """A handler whose first runs fail as an outage would."""

    def __init__(self, inner: AccountDataHandler, failures: int) -> None:
        self._inner = inner
        self._failures = failures
        self.calls = 0

    @property
    def owner(self) -> str:
        return self._inner.owner

    def export(self, account: AccountRef) -> AsyncIterator[ExportFile]:
        return self._inner.export(account)

    async def erase(self, account: AccountRef) -> None:
        self.calls += 1
        if self.calls <= self._failures:
            message = "хранилище не ответило"
            raise ConnectionError(message)
        await self._inner.erase(account)


def erasure_of(
    bench: RegistrationBench, homes: DatabaseAccess, objects: Mapping[Home, ObjectStorage],
    core: AccountDataHandler | None = None,
) -> Erasure:  # fmt: skip
    transactions = homes.transactions
    identity = IdentityAccountData(transactions, bench.services.directory, objects)
    ports = PortDirectory()
    ports.install(
        [
            ACCOUNT_DATA_HANDLERS.bind(core or CoreAccountData(transactions)),
            ACCOUNT_DATA_HANDLERS.bind(identity),
        ]
    )
    outbox = EventOutbox(EventTypes(list(IDENTITY_EVENTS)))
    return Erasure(transactions, ports, outbox, DeletionMetrics(CollectorRegistry()))


async def due_deletion(bench: RegistrationBench, run_slot: RunSlot) -> UUID:
    """An account with an avatar and a consent change whose deletion window has passed."""
    user_id = await account(bench, run_slot)
    headers = bearer((await login(bench))["access_token"])
    await bench.http.put("/v1/me/avatar", content=png(), headers=headers)
    await bench.http.patch("/v1/me", headers=headers, json={"consents": {"marketing": True}})
    await ask(bench, headers["Authorization"].removeprefix("Bearer "))
    await run_slot.claimed.connections[Home.RU].execute(
        "UPDATE account_deletions SET requested_at = requested_at - interval '8 days', "
        "erase_at = erase_at - interval '8 days', run_at = run_at - interval '8 days'"
    )
    return user_id


def bucket_objects(buckets: Mapping[Home, SlotBucket]) -> dict[Home, ObjectStorage]:
    return {home: slot_storage(bucket).objects for home, bucket in buckets.items()}


async def test_on_day_8_nothing_of_the_person_remains_and_the_address_is_free(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis,
    buckets: Mapping[Home, SlotBucket],
) -> None:  # fmt: skip
    objects = bucket_objects(buckets)
    options = BenchOptions(objects=objects)
    async with registration_bench(homes.transactions, valkey, redis_cache, options) as bench:
        erased = await due_deletion(bench, run_slot)
        archive = f"exports/{erased}/archive.zip"
        await objects[Home.RU].put(archive, b"PK", content_type="application/zip")
        erasure = erasure_of(bench, homes, objects)
        due = await erasure.start_due(Home.RU)
        for user_id in due:
            await erasure.erase(AccountRef(user_id, Home.RU))
        stale = await bench.http.post("/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})
        again = await account(bench, run_slot)
        avatars = [item async for item in objects[Home.RU].list_objects("avatars/")]
        archives = [item async for item in objects[Home.RU].list_objects("exports/")]

    connection = run_slot.claimed.connections[Home.RU]
    rows_of = sql.SQL("SELECT 1 FROM {} WHERE user_id = %s")
    left = {
        table: len(await fetch_rows(connection, rows_of.format(sql.Identifier(table)), (erased,)))
        for table in ERASED_TABLES
    }
    [user] = await fetch_rows(
        connection, "SELECT email, password_hash, state FROM users WHERE id = %s", (erased,)
    )
    directory = await fetch_rows(
        run_slot.claimed.connections[Home.EU], "SELECT user_id, state FROM directory_entries"
    )
    assert due == [erased]
    assert stale.status_code == 401
    assert left == dict.fromkeys(ERASED_TABLES, 0)
    assert user == {
        "email": f"deleted-{erased.hex}@deleted.invalid", "password_hash": None, "state": "deleted",
    }  # fmt: skip
    assert avatars == []
    assert archives == []
    assert [(row["user_id"], row["state"]) for row in directory] == [(again, "active")]
    assert "identity.account.deleted" in await events(run_slot)


async def test_a_handler_failing_twice_then_succeeding_leaves_one_result(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis,
    buckets: Mapping[Home, SlotBucket],
) -> None:  # fmt: skip
    objects = bucket_objects(buckets)
    options = BenchOptions(objects=objects)
    async with registration_bench(homes.transactions, valkey, redis_cache, options) as bench:
        erased = await due_deletion(bench, run_slot)
        flaky = Flaky(CoreAccountData(homes.transactions), failures=2)
        erasure = erasure_of(bench, homes, objects, flaky)
        await erasure.start_due(Home.RU)
        target = AccountRef(erased, Home.RU)
        for _ in range(2):
            with pytest.raises(ConnectionError):
                await erasure.erase(target)
        await erasure.erase(target)
        await erasure.erase(target)

    connection = run_slot.claimed.connections[Home.RU]
    [user] = await fetch_rows(connection, "SELECT state FROM users WHERE id = %s", (erased,))
    deleted = [name for name in await events(run_slot) if name == "identity.account.deleted"]
    assert flaky.calls == 3
    assert user["state"] == "deleted"
    assert deleted == ["identity.account.deleted"]


async def test_a_sign_in_holding_the_account_keeps_the_saga_from_starting(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis,
    buckets: Mapping[Home, SlotBucket],
) -> None:  # fmt: skip
    objects = bucket_objects(buckets)
    options = BenchOptions(objects=objects)
    async with registration_bench(homes.transactions, valkey, redis_cache, options) as bench:
        erased = await due_deletion(bench, run_slot)
        erasure = erasure_of(bench, homes, objects)
        connection = run_slot.claimed.connections[Home.RU]
        async with connection.transaction():
            await connection.execute("SELECT 1 FROM users WHERE id = %s FOR UPDATE", (erased,))
            held = await erasure.start_due(Home.RU)
        await connection.execute("UPDATE account_deletions SET run_at = now()")
        free = await erasure.start_due(Home.RU)

    assert held == []
    assert free == [erased]
