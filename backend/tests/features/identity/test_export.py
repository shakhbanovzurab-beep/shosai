"""The export archive of everything Shosai keeps about a person (identity step 7b)."""

import io
import zipfile
from collections.abc import Mapping
from uuid import UUID

import httpx
from redis.asyncio import Redis

from shosai.composition.features import FEATURES, account_data_specs
from shosai.core.account_data.handlers import ACCOUNT_DATA_HANDLERS
from shosai.core.account_data.spec import Treatment
from shosai.core.email.account_data import CoreAccountData
from shosai.core.events.catalog import EventTypes
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.homes import Home
from shosai.core.ports.directory import PortDirectory
from shosai.features.billing.application.account_data import BillingAccountData
from shosai.features.files.application.account_data import FilesAccountData
from shosai.features.identity.application.account_data import IdentityAccountData
from shosai.features.identity.application.export_runner import ExportRunner
from shosai.features.workspaces.application.account_data import WorkspacesAccountData
from shosai.features.workspaces.infrastructure.audit_log import WorkspaceAuditLog
from tests.core.storage.adapters import slot_storage
from tests.features.identity.registration_bench import (
    BenchOptions,
    RegistrationBench,
    registration_bench,
)
from tests.features.identity.test_profile import bearer, png
from tests.features.identity.test_sign_in import EMAIL, account, login
from tests.harness.connections import fetch_rows
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot
from tests.harness.shared_services import SlotBucket

OTHER_EMAIL = "someone.else@example.com"


def runner_of(
    bench: RegistrationBench, homes: DatabaseAccess, buckets: Mapping[Home, SlotBucket]
) -> ExportRunner:
    storages = {home: slot_storage(bucket) for home, bucket in buckets.items()}
    objects = {home: storage.objects for home, storage in storages.items()}
    uploads = {home: storage.uploads for home, storage in storages.items()}
    identity = IdentityAccountData(homes.transactions, bench.services.directory, (objects, uploads))
    ports = PortDirectory()
    ports.install(
        [
            ACCOUNT_DATA_HANDLERS.bind(CoreAccountData(homes.transactions)),
            ACCOUNT_DATA_HANDLERS.bind(identity),
            ACCOUNT_DATA_HANDLERS.bind(
                WorkspacesAccountData(
                    homes.transactions, EventOutbox(EventTypes([])), WorkspaceAuditLog()
                )
            ),
            ACCOUNT_DATA_HANDLERS.bind(BillingAccountData(homes.transactions)),
            ACCOUNT_DATA_HANDLERS.bind(FilesAccountData(homes.transactions, (objects, uploads))),
        ]
    )
    return ExportRunner(homes.transactions, ports, (objects, uploads), bench.services.email)


async def run_due(runner: ExportRunner) -> list[UUID]:
    jobs = await runner.start_due(Home.RU)
    for job_id in jobs:
        await runner.make(Home.RU, job_id)
    return jobs


async def test_the_archive_has_every_covered_table_and_nothing_of_another_account(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis,
    buckets: Mapping[Home, SlotBucket],
) -> None:  # fmt: skip
    objects = {home: slot_storage(bucket).objects for home, bucket in buckets.items()}
    options = BenchOptions(objects=objects)
    async with registration_bench(homes.transactions, valkey, redis_cache, options) as bench:
        other = await account(bench, run_slot, email=OTHER_EMAIL)
        await account(bench, run_slot)
        headers = bearer((await login(bench))["access_token"])
        await bench.http.put("/v1/me/avatar", content=png(), headers=headers)
        first = (await bench.http.post("/v1/me/exports", headers=headers)).json()
        again = (await bench.http.post("/v1/me/exports", headers=headers)).json()
        jobs = await run_due(runner_of(bench, homes, buckets))
        latest = (await bench.http.get("/v1/me/exports/latest", headers=headers)).json()
    async with httpx.AsyncClient() as http:
        archive = zipfile.ZipFile(io.BytesIO((await http.get(latest["download_url"])).content))

    covered = {
        f"{spec.owner}/{coverage.table}.jsonl"
        for spec in account_data_specs(FEATURES)
        for coverage in spec.tables
        if coverage.treatment is not Treatment.EXPIRES
    }
    names = set(archive.namelist())
    everything = b"".join(archive.read(name) for name in names)
    mailed = await fetch_rows(
        run_slot.claimed.connections[Home.RU],
        "SELECT 1 FROM email_messages WHERE template = 'identity.export_ready'",
    )
    assert (first["state"], again["id"]) == ("queued", first["id"])
    assert jobs == [UUID(first["id"])]
    assert latest["state"] == "ready"
    assert covered | {"manifest.json"} <= names
    assert any(name.startswith("identity/avatars/") for name in names)
    assert EMAIL.encode() in archive.read("identity/users.jsonl")
    assert b"password_hash" not in everything
    assert str(other).encode() not in everything
    assert OTHER_EMAIL.encode() not in everything
    assert len(mailed) == 1


async def test_a_fourth_request_in_a_day_is_refused(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        await account(bench, run_slot)
        headers = bearer((await login(bench))["access_token"])
        missing = await bench.http.get("/v1/me/exports/latest", headers=headers)
        answers = []
        for _ in range(4):
            answers.append(await bench.http.post("/v1/me/exports", headers=headers))
            await run_slot.claimed.connections[Home.RU].execute(
                "UPDATE data_export_jobs SET state = 'failed', error_code = 'export_failed' "
                "WHERE state = 'queued'"
            )

    assert (missing.status_code, missing.json()["error"]["code"]) == (404, "export_not_found")
    assert [answer.status_code for answer in answers] == [202, 202, 202, 429]
    assert answers[-1].json()["error"]["code"] == "export_limit"


async def test_a_kept_archive_goes_after_7_days_and_a_stuck_job_is_given_up(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis,
    buckets: Mapping[Home, SlotBucket],
) -> None:  # fmt: skip
    connection = run_slot.claimed.connections[Home.RU]
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        await account(bench, run_slot)
        headers = bearer((await login(bench))["access_token"])
        runner = runner_of(bench, homes, buckets)
        await bench.http.post("/v1/me/exports", headers=headers)
        await run_due(runner)
        await connection.execute(
            "UPDATE data_export_jobs SET expires_at = now() - interval '1 minute'"
        )
        expired = (await bench.http.get("/v1/me/exports/latest", headers=headers)).json()
        purged = await runner.purge(Home.RU)
        await bench.http.post("/v1/me/exports", headers=headers)
        await connection.execute("UPDATE data_export_jobs SET attempts = 3")
        given_up = await runner.start_due(Home.RU)

    archives = [
        item async for item in slot_storage(buckets[Home.RU]).objects.list_objects("exports/")
    ]
    [job] = await fetch_rows(connection, "SELECT state, error_code FROM data_export_jobs")
    assert expired["download_url"] is None
    assert purged == 1
    assert archives == []
    assert given_up == []
    assert job == {"state": "failed", "error_code": "export_failed"}
