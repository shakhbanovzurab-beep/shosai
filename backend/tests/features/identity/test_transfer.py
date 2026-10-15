"""The account transfer saga between the homes (identity step 9, §6)."""

from collections.abc import Mapping
from uuid import UUID

import pytest
from prometheus_client import CollectorRegistry
from redis.asyncio import Redis

from shosai.core.account_data.handlers import ACCOUNT_DATA_HANDLERS, AccountRef
from shosai.core.email.account_data import CoreAccountData
from shosai.core.events.catalog import EventTypes
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.homes import Home
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.application.account_data import IdentityAccountData
from shosai.features.identity.application.transfer_saga import SagaServices, TransferSaga
from shosai.features.identity.application.transfers import Transfers
from shosai.features.identity.contracts import IDENTITY_EVENTS
from shosai.features.identity.domain.transfer import FINISHED, TransferStep
from shosai.features.identity.infrastructure.transfer_metrics import TransferMetrics
from tests.core.storage.adapters import slot_storage
from tests.features.identity.admin_bench import sign_in_admin
from tests.features.identity.registration_bench import (
    BenchOptions,
    RegistrationBench,
    registration_bench,
)
from tests.features.identity.test_profile import bearer, png
from tests.features.identity.test_sign_in import account, login
from tests.harness.connections import fetch_rows
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot
from tests.harness.shared_services import SlotBucket


class Mover:
    """The saga and the admin's service over both homes of the slot."""

    def __init__(
        self, bench: RegistrationBench, homes: DatabaseAccess, buckets: Mapping[Home, SlotBucket]
    ) -> None:
        storages = {home: slot_storage(bucket) for home, bucket in buckets.items()}
        self.objects = {home: storage.objects for home, storage in storages.items()}
        uploads = {home: storage.uploads for home, storage in storages.items()}
        transactions, directory = homes.transactions, bench.services.directory
        self.handlers = (
            CoreAccountData(transactions),
            IdentityAccountData(transactions, directory, (self.objects, uploads)),
        )
        ports = PortDirectory()
        ports.install([ACCOUNT_DATA_HANDLERS.bind(handler) for handler in self.handlers])
        outbox = EventOutbox(EventTypes(list(IDENTITY_EVENTS)))
        self.saga = TransferSaga(
            SagaServices(
                transactions=transactions, ports=ports, directory=directory,
                markers=bench.markers, outbox=outbox,
                metrics=TransferMetrics(CollectorRegistry()),
            )
        )  # fmt: skip
        self.transfers = Transfers(transactions, directory, outbox, allowed=True)

    async def manifest(self, user_id: UUID, home: Home) -> dict[str, Mapping[str, str]]:
        account = AccountRef(user_id, home)
        return {handler.owner: await handler.manifest(account) for handler in self.handlers}

    async def avatars(self, home: Home) -> list[str]:
        return [item.key async for item in self.objects[home].list_objects("avatars/")]


async def prepared(bench: RegistrationBench, run_slot: RunSlot) -> tuple[UUID, dict[str, str]]:
    """An account in the Russian home with an avatar and a consent change, and its token."""
    user_id = await account(bench, run_slot)
    headers = bearer((await login(bench))["access_token"])
    await bench.http.put("/v1/me/avatar", content=png(), headers=headers)
    await bench.http.patch("/v1/me", headers=headers, json={"consents": {"marketing": True}})
    return user_id, headers


def without_account_row(manifest: dict[str, Mapping[str, str]]) -> dict[str, Mapping[str, str]]:
    """The manifest but the account row, whose token version every transfer bumps."""
    return {
        owner: {name: digest for name, digest in digests.items() if name != "users"}
        for owner, digests in manifest.items()
    }


async def row_count(run_slot: RunSlot, home: Home, user_id: UUID) -> int:
    rows = await fetch_rows(
        run_slot.claimed.connections[home], "SELECT 1 FROM users WHERE id = %s", (user_id,)
    )
    return len(rows)


async def test_a_transfer_there_and_back_leaves_the_same_data_and_ends_old_tokens(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis,
    buckets: Mapping[Home, SlotBucket],
) -> None:  # fmt: skip
    objects = {home: slot_storage(bucket).objects for home, bucket in buckets.items()}
    options = BenchOptions(objects=objects)
    async with registration_bench(homes.transactions, valkey, redis_cache, options) as bench:
        mover = Mover(bench, homes, buckets)
        user_id, old = await prepared(bench, run_slot)
        before = await mover.manifest(user_id, Home.RU)
        there = await mover.transfers.request(user_id, Home.EU)
        await mover.saga.run(Home.RU, there.id)
        away = (await mover.transfers.view(there.id), await mover.avatars(Home.EU))
        moved_rows = (await row_count(run_slot, Home.RU, user_id), await mover.avatars(Home.RU))
        stale = await bench.http.get("/v1/me", headers=old)
        back = await mover.transfers.request(user_id, Home.RU)
        await mover.saga.run(Home.EU, back.id)
        after = await mover.manifest(user_id, Home.RU)

    [directory] = await fetch_rows(
        run_slot.claimed.connections[Home.EU], "SELECT home FROM directory_entries"
    )
    assert away[0].step is TransferStep.DONE
    assert len(away[1]) == 1
    assert moved_rows == (0, [])
    assert stale.status_code == 401
    assert without_account_row(after) == without_account_row(before)
    assert directory["home"] == "ru"
    assert await row_count(run_slot, Home.EU, user_id) == 0


async def test_a_crash_after_every_step_resumes_to_the_same_end(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis,
    buckets: Mapping[Home, SlotBucket],
) -> None:  # fmt: skip
    objects = {home: slot_storage(bucket).objects for home, bucket in buckets.items()}
    options = BenchOptions(objects=objects)
    connection = run_slot.claimed.connections[Home.RU]
    async with registration_bench(homes.transactions, valkey, redis_cache, options) as bench:
        mover = Mover(bench, homes, buckets)
        user_id, _ = await prepared(bench, run_slot)
        [user] = await fetch_rows(connection, "SELECT token_version FROM users")
        before = await mover.manifest(user_id, Home.RU)
        transfer = await mover.transfers.request(user_id, Home.EU)
        steps = []
        while (current := (await mover.transfers.view(transfer.id)).step) not in FINISHED:
            steps.append(current)
            await mover.saga.step(Home.RU, transfer.id)
            # Сбой после работы шага, до его записи: журнал снова называет этот шаг.
            await connection.execute(
                "UPDATE home_transfers SET step = %s, finished_at = NULL WHERE id = %s",
                (current.value, transfer.id),
            )
            await mover.saga.step(Home.RU, transfer.id)
        after = await mover.manifest(user_id, Home.EU)

    [moved] = await fetch_rows(
        run_slot.claimed.connections[Home.EU], "SELECT token_version, state FROM users"
    )
    transferred = await fetch_rows(
        run_slot.claimed.connections[Home.EU],
        "SELECT 1 FROM outbox_messages WHERE event_type = 'identity.account.transferred'",
    )
    assert steps == [
        TransferStep.FREEZE, TransferStep.COPY, TransferStep.VERIFY, TransferStep.SWITCH,
        TransferStep.BUMP, TransferStep.PURGE,
    ]  # fmt: skip
    assert without_account_row(after) == without_account_row(before)
    assert moved == {"token_version": user["token_version"] + 1, "state": "active"}
    assert len(transferred) == 1
    assert await row_count(run_slot, Home.RU, user_id) == 0


async def test_a_cancel_before_the_switch_leaves_the_source_untouched(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis,
    buckets: Mapping[Home, SlotBucket],
) -> None:  # fmt: skip
    objects = {home: slot_storage(bucket).objects for home, bucket in buckets.items()}
    options = BenchOptions(objects=objects)
    async with registration_bench(homes.transactions, valkey, redis_cache, options) as bench:
        mover = Mover(bench, homes, buckets)
        user_id, headers = await prepared(bench, run_slot)
        before = await mover.manifest(user_id, Home.RU)
        transfer = await mover.transfers.request(user_id, Home.EU)
        for _ in range(2):
            await mover.saga.step(Home.RU, transfer.id)
        copied = await row_count(run_slot, Home.EU, user_id)
        await mover.transfers.cancel(transfer.id)
        await mover.saga.run(Home.RU, transfer.id)
        ended = await mover.transfers.view(transfer.id)
        me = await bench.http.get("/v1/me", headers=headers)
        after = await mover.manifest(user_id, Home.RU)
        late = await mover.transfers.request(user_id, Home.EU)
        while (await mover.transfers.view(late.id)).step is not TransferStep.BUMP:
            await mover.saga.step(Home.RU, late.id)
        with pytest.raises(AppError, match="transfer_not_cancellable"):
            await mover.transfers.cancel(late.id)
        avatars_eu_after_cancel = len(await mover.avatars(Home.EU))

    assert copied == 1
    assert ended.step is TransferStep.CANCELLED
    assert me.status_code == 200
    assert after == before
    assert avatars_eu_after_cancel == 1


async def test_transfers_stay_closed_until_the_legal_review(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        user_id = await account(bench, run_slot)
        await sign_in_admin(bench.http)
        closed = await bench.http.post(
            f"/v1/admin/users/{user_id}/transfers", json={"to_home": "eu"}
        )
        missing = await bench.http.get(f"/v1/admin/transfers/{UUID(int=7)}")

    assert (closed.status_code, closed.json()["error"]["code"]) == (409, "transfers_closed")
    assert (missing.status_code, missing.json()["error"]["code"]) == (404, "transfer_not_found")
