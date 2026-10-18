"""The quota (files step 5, FL-D2): reservations under concurrency, the 90 days over the
limit with three reminders, the removal of the newest files, the mark cleared, inv-11.
"""

import asyncio
import uuid
from collections.abc import Mapping
from datetime import timedelta

from sqlalchemy.dialects.postgresql import insert

from shosai.core.config.roles import ProcessRole
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.homes import Home
from shosai.features.files.application.quota_sweep import QuotaSweep
from shosai.features.files.application.upload_links import StorageOfHomes
from shosai.features.files.application.upload_rules import UploadRequest
from shosai.features.files.application.uploads import UploadService
from shosai.features.files.domain.purposes import UploadPurpose
from shosai.features.files.domain.quota import QuotaAction
from shosai.features.files.infrastructure.file_records import StorageFileRecord
from shosai.features.files.infrastructure.object_deleter import ObjectDeleter
from shosai.features.files.infrastructure.upload_records import StorageUsageRecord
from shosai.features.identity.contracts import Principal
from tests.core.storage.adapters import slot_storage
from tests.features.files.file_bench import FileBench
from tests.features.files.upload_bench import GIB, person
from tests.harness.connections import fetch_value
from tests.harness.database_access import (
    DatabaseAccess,
    ProcessShape,
    open_database_access,
    slot_urls,
)
from tests.harness.run_slot import RunSlot
from tests.harness.shared_services import SlotBucket

REMINDER_COUNT_SQL = (
    "SELECT count(*) FROM email_messages WHERE template = 'files.storage_over_limit'"
)


async def seed(bench: FileBench, who: Principal, sizes: list[int]) -> list[uuid.UUID]:
    """Files of the given sizes, oldest first, and the counter that sums them."""
    ids = [uuid.uuid4() for _ in sizes]
    start = bench.uploads.clock.now - timedelta(days=30)
    async with bench.uploads.transactions.begin(who.scope()) as session:
        for number, (file_id, size) in enumerate(zip(ids, sizes, strict=True)):
            moment = start + timedelta(minutes=number)
            session.add(
                StorageFileRecord(
                    id=file_id, user_id=who.user_id, name=f"File {number}.pdf",
                    content_type="application/pdf", size_bytes=size,
                    object_key=f"u/{who.user_id}/f/{file_id}", created_at=moment,
                    modified_at=moment,
                )
            )  # fmt: skip
        await session.execute(
            insert(StorageUsageRecord).values(user_id=who.user_id, used_bytes=sum(sizes))
        )
    return ids


async def sweep(bench: FileBench, run_slot: RunSlot, home: Home) -> int:
    """The daily pass as the workers run it."""
    async with open_database_access(
        slot_urls(run_slot), ProcessShape(role=ProcessRole.WORKERS)
    ) as workers:
        return await QuotaSweep(workers.transactions, bench.watch, bench.uploads.clock).run(home)


async def reminders(run_slot: RunSlot, home: Home) -> int:
    count = await fetch_value(run_slot.claimed.connections[home], REMINDER_COUNT_SQL)
    assert isinstance(count, int)
    return count


async def test_concurrent_uploads_never_pass_the_limit(
    file_bench: FileBench, homes: DatabaseAccess, buckets: Mapping[Home, SlotBucket]
) -> None:
    who = person(Home.RU, uuid.uuid4())
    await seed(file_bench, who, [GIB - 1000])
    # Без охранников стенда: параллельные запросы делят их счётчик открытых транзакций.
    storages = {home: slot_storage(bucket) for home, bucket in buckets.items()}
    objects = {home: storage.objects for home, storage in storages.items()}
    service = UploadService(
        homes.transactions,
        StorageOfHomes(objects, {home: s.uploads for home, s in storages.items()}),
        (file_bench.ports, ObjectDeleter(homes.transactions, objects)),
    )
    request = UploadRequest(UploadPurpose.FILE_MANAGER, "Part.pdf", "application/pdf", 400)

    results = await asyncio.gather(
        *(service.create(who, request) for _ in range(5)), return_exceptions=True
    )

    refused = [r for r in results if isinstance(r, AppError) and r.code == "storage_limit"]
    assert (len(results) - len(refused), len(refused)) == (2, 3)
    async with homes.transactions.begin(who.scope(), read_only=True) as session:
        row = await session.get(StorageUsageRecord, who.user_id)
    assert row is not None
    assert (row.used_bytes, row.reserved_bytes) == (GIB - 1000, 800)


async def test_over_the_limit_nothing_goes_for_90_days_and_each_reminder_goes_once(
    file_bench: FileBench, run_slot: RunSlot
) -> None:
    who = person(Home.RU, uuid.uuid4())
    ids = await seed(file_bench, who, [400 * 1024**2] * 3)
    file_bench.uploads.plan.file_manager_gb = 1
    clock = file_bench.uploads.clock
    start = clock.now

    marked = await sweep(file_bench, run_slot, Home.RU)
    standing = await file_bench.watch.standing(Home.RU, who.user_id)
    counted: list[int] = []
    for day in (59, 60, 60, 83, 89):
        clock.now = start + timedelta(days=day)
        await sweep(file_bench, run_slot, Home.RU)
        counted.append(await reminders(run_slot, Home.RU))
    _, kept = await file_bench.manager.listing(who)
    refused = None
    try:
        await file_bench.uploaded(who, "More.pdf", b"x" * 10)
    except AppError as error:
        refused = error.code

    assert marked == 1
    assert standing.over_limit_since == start
    assert standing.removal_at == start + timedelta(days=90)
    assert counted == [0, 1, 1, 2, 3]
    assert {view.id for view in kept} == set(ids)
    assert refused == "storage_limit"


async def test_on_day_90_exactly_the_newest_files_over_the_limit_go_and_the_mark_clears(
    file_bench: FileBench, run_slot: RunSlot
) -> None:
    who = person(Home.EU, uuid.uuid4())
    oldest, middle, newest = await seed(file_bench, who, [400 * 1024**2] * 3)
    clock = file_bench.uploads.clock
    start = clock.now
    await sweep(file_bench, run_slot, Home.EU)

    clock.now = start + timedelta(days=90)
    await sweep(file_bench, run_slot, Home.EU)
    _, kept = await file_bench.manager.listing(who)
    standing = await file_bench.watch.standing(Home.EU, who.user_id)
    [hidden] = await file_bench.hidden.of_person(Home.EU, who.user_id)

    assert {view.id for view in kept} == {oldest, middle}
    assert hidden.file_id == newest
    assert (standing.used_bytes, standing.over_limit_since) == (800 * 1024**2, None)
    assert "files.file.deleted" in await file_bench.events(who)


async def test_back_under_the_limit_the_mark_clears_and_a_restore_over_it_marks_again(
    file_bench: FileBench, run_slot: RunSlot
) -> None:
    who = person(Home.RU, uuid.uuid4())
    *_, last = await seed(file_bench, who, [400 * 1024**2] * 3)
    await sweep(file_bench, run_slot, Home.RU)

    await file_bench.manager.delete(who, last)
    await sweep(file_bench, run_slot, Home.RU)
    cleared = await file_bench.watch.standing(Home.RU, who.user_id)
    await file_bench.hidden.restore(Home.RU, who.user_id, last)
    restored = await file_bench.watch.standing(Home.RU, who.user_id)
    file_bench.uploads.plan.file_manager_gb = 2
    async with file_bench.uploads.transactions.begin(who.scope()) as session:
        upgraded = await file_bench.watch.apply(
            session, who.user_id, await file_bench.watch.limit(Home.RU, who.user_id)
        )

    assert cleared.over_limit_since is None
    assert restored.over_limit_since == file_bench.uploads.clock.now
    assert upgraded is QuotaAction.CLEAR


async def test_unknown_entitlements_answer_503_and_leave_the_person_for_tomorrow(
    file_bench: FileBench, run_slot: RunSlot
) -> None:
    who = person(Home.RU, uuid.uuid4())
    await seed(file_bench, who, [2 * GIB])
    file_bench.uploads.plan.unavailable = True

    taken = await sweep(file_bench, run_slot, Home.RU)
    errors: list[tuple[str, int]] = []
    for call in (
        file_bench.watch.standing(Home.RU, who.user_id),
        file_bench.manager.copy(who, (await file_bench.manager.listing(who))[1][0].id, None),
    ):
        try:
            await call
        except AppError as error:
            errors.append((error.code, int(error.status)))

    assert taken == 0
    assert errors == [("entitlements_unavailable", 503)] * 2
