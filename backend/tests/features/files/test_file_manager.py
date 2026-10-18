"""The File Manager: files from uploads, edits, copies on one object, deletion hidden for 7
days, support's restore, the purge and downloads through the edge (files step 4; FL-D4/5/9).
"""

import uuid
from collections.abc import Mapping
from datetime import timedelta

import httpx
import pytest
from sqlalchemy import select, update

from shosai.core.config.roles import ProcessRole
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.files.application.file_manager import FileChanges
from shosai.features.files.application.hidden_files import HiddenFiles
from shosai.features.files.infrastructure.file_records import StorageFileRecord
from shosai.features.files.infrastructure.upload_records import (
    ObjectDeletionRecord,
    StorageUsageRecord,
)
from shosai.features.identity.contracts import Principal
from tests.features.files.file_bench import EDGE, FileBench
from tests.features.files.upload_bench import GIB, person
from tests.harness.database_access import ProcessShape, open_database_access, slot_urls
from tests.harness.run_slot import RunSlot
from tests.harness.shared_services import SlotBucket

BODY = b"%PDF report" * 30


async def key_of(bench: FileBench, who: Principal, file_id: uuid.UUID) -> str:
    async with bench.uploads.transactions.begin(who.scope(), read_only=True) as session:
        key = await session.scalar(
            select(StorageFileRecord.object_key).where(StorageFileRecord.id == file_id)
        )
    assert key is not None
    return key


async def purge(bench: FileBench, run_slot: RunSlot, home: Home) -> int:
    """A purge pass as the workers run it, a week after now."""
    bench.uploads.clock.now += timedelta(days=8)
    async with open_database_access(
        slot_urls(run_slot), ProcessShape(role=ProcessRole.WORKERS)
    ) as workers:
        hidden = HiddenFiles(
            workers.transactions,
            (bench.outbox, bench.uploads.deleter, bench.watch),
            bench.uploads.clock,
        )
        return await hidden.purge(home)


async def test_uploads_become_files_once_and_count_as_used(file_bench: FileBench) -> None:
    who = person(Home.RU, uuid.uuid4())
    first = await file_bench.uploaded(who, "Plan.pdf", BODY)
    second = await file_bench.uploaded(who, "Budget.pdf", BODY[:100])

    made = await file_bench.manager.register(who, [first, second], None)
    again = await file_bench.manager.register(who, [first, second], None)
    folders, files = await file_bench.manager.listing(who)

    assert [view.id for view in made] == [view.id for view in again] == [first, second]
    assert {view.id for view in files} == {first, second}
    assert folders == []
    assert await file_bench.used(who) == len(BODY) + 100
    assert await file_bench.events(who) == ["files.file.uploaded", "files.file.uploaded"]
    with pytest.raises(AppError, match="upload_count"):
        await file_bench.manager.register(who, [], None)


async def test_files_are_renamed_moved_starred_and_folders_keep_them_on_delete(
    file_bench: FileBench,
) -> None:
    who, stranger = person(Home.EU, uuid.uuid4()), person(Home.EU, uuid.uuid4())
    file = await file_bench.file(who, "Plan.pdf", BODY)
    folder = await file_bench.folders.create(who, "Projects")
    theirs = await file_bench.folders.create(stranger, "Theirs")

    moved = await file_bench.manager.update(
        who, file.id, FileChanges(name="Plan v2.pdf", move=True, folder_id=folder.id, starred=True)
    )
    renamed = await file_bench.folders.rename(who, folder.id, "Archive")
    await file_bench.folders.delete(who, folder.id)
    _, [rooted] = await file_bench.manager.listing(who)

    assert (moved.name, moved.folder_id, moved.starred) == ("Plan v2.pdf", folder.id, True)
    assert renamed.name == "Archive"
    assert (rooted.id, rooted.folder_id) == (file.id, None)
    with pytest.raises(AppError, match="folder_not_found"):
        await file_bench.manager.update(who, file.id, FileChanges(move=True, folder_id=theirs.id))
    with pytest.raises(AppError, match="file_not_found"):
        await file_bench.manager.update(stranger, file.id, FileChanges(starred=False))
    with pytest.raises(AppError, match="folder_not_found"):
        await file_bench.folders.rename(stranger, folder.id, "Mine")


async def test_a_deleted_file_is_hidden_out_of_the_quota_restorable_then_purged(
    file_bench: FileBench, run_slot: RunSlot
) -> None:
    who = person(Home.RU, uuid.uuid4())
    file = await file_bench.file(who, "Plan.pdf", BODY)
    key = await key_of(file_bench, who, file.id)
    objects = file_bench.uploads.objects[Home.RU]

    await file_bench.manager.delete(who, file.id)
    _, after_delete = await file_bench.manager.listing(who)
    used_after_delete = await file_bench.used(who)
    [kept] = await file_bench.hidden.of_person(Home.RU, who.user_id)
    with pytest.raises(AppError, match="file_not_found"):
        await file_bench.downloads.link(who, file.id)
    await file_bench.hidden.restore(Home.RU, who.user_id, file.id)
    _, after_restore = await file_bench.manager.listing(who)
    used_after_restore = await file_bench.used(who)
    await file_bench.manager.delete(who, file.id)
    purged = await purge(file_bench, run_slot, Home.RU)

    assert (after_delete, used_after_delete) == ([], 0)
    assert (kept.file_id, kept.size_bytes) == (file.id, len(BODY))
    assert ([view.id for view in after_restore], used_after_restore) == ([file.id], len(BODY))
    assert purged == 1
    assert await objects.head(key) is None
    assert await file_bench.hidden.of_person(Home.RU, who.user_id) == []
    assert await file_bench.events(who) == [
        "files.file.uploaded", "files.file.deleted", "files.file.restored", "files.file.deleted",
    ]  # fmt: skip
    with pytest.raises(AppError, match="hidden_file_not_found"):
        await file_bench.hidden.restore(Home.RU, who.user_id, file.id)


async def test_a_copy_shares_the_object_outlives_the_source_and_goes_with_the_last_row(
    file_bench: FileBench, run_slot: RunSlot
) -> None:
    who = person(Home.EU, uuid.uuid4())
    source = await file_bench.file(who, "Report.pdf", BODY)
    copy = await file_bench.manager.copy(who, source.id, None)
    named = await file_bench.manager.copy(who, source.id, "Mine.pdf")
    key = await key_of(file_bench, who, source.id)
    copy_key = await key_of(file_bench, who, copy.id)
    objects = file_bench.uploads.objects[Home.EU]

    await file_bench.manager.delete(who, source.id)
    await file_bench.manager.delete(who, named.id)
    await purge(file_bench, run_slot, Home.EU)
    survived = await objects.head(key)
    await file_bench.manager.delete(who, copy.id)
    await purge(file_bench, run_slot, Home.EU)

    assert (copy.name, named.name) == ("Report (2).pdf", "Mine.pdf")
    assert copy_key == key
    assert survived is not None
    assert await objects.head(key) is None


async def test_a_copy_needs_room_in_the_plan(file_bench: FileBench) -> None:
    who = person(Home.RU, uuid.uuid4())
    source = await file_bench.file(who, "Report.pdf", BODY)
    async with file_bench.uploads.transactions.begin(who.scope()) as session:
        await session.execute(
            update(StorageUsageRecord)
            .where(StorageUsageRecord.user_id == who.user_id)
            .values(used_bytes=GIB - 10)
        )

    with pytest.raises(AppError, match="storage_limit"):
        await file_bench.manager.copy(who, source.id, None)
    file_bench.uploads.plan.file_manager_gb = 0
    with pytest.raises(AppError, match="storage_not_included"):
        await file_bench.manager.copy(who, source.id, None)
    assert await file_bench.used(who) == GIB - 10


async def test_an_object_the_bucket_refused_to_delete_is_retried_until_gone(
    file_bench: FileBench, run_slot: RunSlot
) -> None:
    who = person(Home.RU, uuid.uuid4())
    file = await file_bench.file(who, "Plan.pdf", BODY)
    key = await key_of(file_bench, who, file.id)
    objects = file_bench.uploads.objects[Home.RU]
    await file_bench.manager.delete(who, file.id)

    file_bench.uploads.guard.failing_deletes = True
    await purge(file_bench, run_slot, Home.RU)
    async with file_bench.uploads.transactions.begin(TenancyScope(Home.RU)) as session:
        waiting = await session.get(ObjectDeletionRecord, key)
    still_there = await objects.head(key)
    file_bench.uploads.guard.failing_deletes = False
    retried = await file_bench.uploads.deleter.retry(Home.RU)

    assert (waiting is not None and waiting.attempts == 1, still_there is not None) == (True, True)
    assert retried >= 1
    assert await objects.head(key) is None


async def test_a_download_link_goes_through_the_edge_with_the_type_pinned(
    file_bench: FileBench, buckets: Mapping[Home, SlotBucket]
) -> None:
    who, stranger = person(Home.EU, uuid.uuid4()), person(Home.EU, uuid.uuid4())
    file = await file_bench.file(who, "Plan.pdf", BODY)

    link = await file_bench.downloads.link(who, file.id)
    # Edge снимает /dl/eu и передаёт остаток бакету дома байт в байт: так же делает тест.
    bucket = buckets[Home.EU].client.meta.endpoint_url.rstrip("/")
    async with httpx.AsyncClient() as client:
        answer = await client.get(bucket + link.url.removeprefix(f"{EDGE}/eu"))

    assert link.url.startswith(f"{EDGE}/eu/")
    assert answer.status_code == 200, answer.text
    assert answer.content == BODY
    assert answer.headers["content-type"] == "application/pdf"
    assert answer.headers["content-disposition"].startswith("inline")
    with pytest.raises(AppError, match="file_not_found"):
        await file_bench.downloads.link(stranger, file.id)
