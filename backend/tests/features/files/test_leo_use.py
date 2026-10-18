"""Leo's use of files (files step 6): switches on files and folders, one event per change of
a file's use, the knowledge limit over the readable files in use, the reindex request.
"""

import asyncio
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.dialects.postgresql import insert

from shosai.core.kernel.errors import AppError
from shosai.core.kernel.homes import Home
from shosai.features.files.application.file_manager import FileChanges
from shosai.features.files.application.file_views import FileView
from shosai.features.files.contracts import IndexStage
from shosai.features.files.domain.leo import LeoVia
from shosai.features.files.infrastructure.file_records import StorageFileRecord
from shosai.features.files.infrastructure.upload_records import StorageUsageRecord
from shosai.features.identity.contracts import Principal
from tests.features.files.file_bench import FileBench
from tests.features.files.upload_bench import person

KB = 1000
MIB = 1024**2


async def seed(bench: FileBench, who: Principal, files: dict[str, int]) -> dict[str, uuid.UUID]:
    """Files of the person by name and size, at the root, Leo off; the counter sums them."""
    ids = {name: uuid.uuid4() for name in files}
    now = datetime.now(UTC)
    async with bench.uploads.transactions.begin(who.scope()) as session:
        for name, size in files.items():
            file_id = ids[name]
            session.add(
                StorageFileRecord(
                    id=file_id, user_id=who.user_id, name=name, content_type="text/plain",
                    size_bytes=size, object_key=f"u/{who.user_id}/f/{file_id}",
                    created_at=now, modified_at=now,
                )
            )  # fmt: skip
        await session.execute(
            insert(StorageUsageRecord).values(user_id=who.user_id, used_bytes=sum(files.values()))
        )
    return ids


def move(folder_id: uuid.UUID | None) -> FileChanges:
    return FileChanges(move=True, folder_id=folder_id)


def via_of(view: FileView) -> LeoVia | None:
    """Why Leo uses the file, or None."""
    return None if view.leo is None else view.leo.via


async def test_moving_into_and_out_of_a_leo_folder_changes_use_and_emits_once(
    file_bench: FileBench,
) -> None:
    who = person(Home.RU, uuid.uuid4())
    notes = (await seed(file_bench, who, {"Notes.txt": 10 * KB}))["Notes.txt"]
    folder = await file_bench.folders.create(who, "For Leo")
    switched = await file_bench.folders.update(who, folder.id, name=None, leo=True)
    manager = file_bench.manager

    moved_in = await manager.update(who, notes, move(folder.id))
    await manager.update(who, notes, move(folder.id))
    await manager.update(who, notes, FileChanges(name="Notes v2.txt"))
    moved_out = await manager.update(who, notes, move(None))
    await manager.update(who, notes, move(None))

    assert switched.leo is True
    assert moved_in.leo is not None
    assert (moved_in.leo.via, moved_in.leo.state.stage) == (LeoVia.FOLDER, IndexStage.QUEUED)
    assert moved_out.leo is None
    assert await file_bench.leo_events(who) == [(notes, True), (notes, False)]


async def test_a_file_s_own_switch_and_its_folder_s_make_one_use(file_bench: FileBench) -> None:
    who = person(Home.EU, uuid.uuid4())
    ids = await seed(file_bench, who, {"Plan.pdf": 10 * KB, "Brief.md": 5 * KB, "Logo.png": KB})
    plan, brief, logo = ids["Plan.pdf"], ids["Brief.md"], ids["Logo.png"]
    folder = await file_bench.folders.create(who, "Project")
    for file_id in ids.values():
        await file_bench.manager.update(who, file_id, move(folder.id))
    marked = await file_bench.manager.update(who, plan, FileChanges(leo=True))

    await file_bench.folders.update(who, folder.id, name=None, leo=True)
    _, listed = await file_bench.manager.listing(who)
    await file_bench.manager.update(who, plan, FileChanges(leo=False))
    await file_bench.manager.update(who, plan, FileChanges(leo=True))
    await file_bench.folders.update(who, folder.id, name=None, leo=False)
    await file_bench.folders.update(who, folder.id, name=None, leo=True)
    await file_bench.folders.delete(who, folder.id)
    _, after = await file_bench.manager.listing(who)

    assert via_of(marked) is LeoVia.FILE
    assert {view.id: via_of(view) for view in listed} == {
        plan: LeoVia.FILE,
        brief: LeoVia.FOLDER,
        logo: None,
    }
    assert {view.id: view.leo is not None for view in after} == {
        plan: True, brief: False, logo: False,
    }  # fmt: skip
    assert await file_bench.leo_events(who) == [
        (plan, True), (brief, True), (brief, False), (brief, True), (brief, False),
    ]  # fmt: skip
    with pytest.raises(AppError, match="leo_unreadable"):
        await file_bench.manager.update(who, logo, FileChanges(leo=True))


async def test_the_knowledge_limit_counts_only_readable_files_in_use(
    file_bench: FileBench,
) -> None:
    who = person(Home.RU, uuid.uuid4())
    file_bench.uploads.plan.knowledge_base_mb = 1
    ids = await seed(
        file_bench, who, {"Video.mov": 900 * KB, "First.txt": 600 * KB, "Second.txt": 600 * KB}
    )
    video, first, second = ids["Video.mov"], ids["First.txt"], ids["Second.txt"]
    folder = await file_bench.folders.create(who, "Leo")
    await file_bench.manager.update(who, video, move(folder.id))
    await file_bench.folders.update(who, folder.id, name=None, leo=True)
    await file_bench.manager.update(who, first, FileChanges(leo=True))

    refusals = []
    # Переименование делает видео читаемым для Leo, и его байты пошли бы в лимит.
    for file_id, changes in (
        (second, FileChanges(leo=True)),
        (second, move(folder.id)),
        (video, FileChanges(name="Video.txt")),
    ):
        with pytest.raises(AppError, match="leo_limit") as refused:
            await file_bench.manager.update(who, file_id, changes)
        refusals.append(refused.value.params["limit_bytes"])
    file_bench.uploads.plan.knowledge_base_mb = 0
    with pytest.raises(AppError, match="leo_limit") as not_included:
        await file_bench.manager.update(who, second, FileChanges(leo=True))
    _, files = await file_bench.manager.listing(who)

    assert (refusals, not_included.value.params["limit_bytes"]) == ([MIB, MIB, MIB], 0)
    assert {view.name for view in files if view.leo is not None} == {"First.txt"}
    assert await file_bench.leo_events(who) == [(first, True)]


async def test_a_lowered_limit_still_lets_leo_stop_using_files(file_bench: FileBench) -> None:
    who = person(Home.EU, uuid.uuid4())
    ids = await seed(file_bench, who, {"A.txt": 600 * KB, "B.txt": 600 * KB})
    for file_id in ids.values():
        await file_bench.manager.update(who, file_id, FileChanges(leo=True))
    file_bench.uploads.plan.knowledge_base_mb = 1

    stopped = await file_bench.manager.update(who, ids["A.txt"], FileChanges(leo=False))
    with pytest.raises(AppError, match="leo_limit"):
        await file_bench.manager.update(who, ids["A.txt"], FileChanges(leo=True))

    assert stopped.leo is None


async def test_concurrent_switches_never_pass_the_limit(file_bench: FileBench) -> None:
    who = person(Home.RU, uuid.uuid4())
    file_bench.uploads.plan.knowledge_base_mb = 1
    ids = await seed(file_bench, who, {f"Part {n}.txt": 400 * KB for n in range(5)})

    results = await asyncio.gather(
        *(file_bench.manager.update(who, i, FileChanges(leo=True)) for i in ids.values()),
        return_exceptions=True,
    )

    refused = [r for r in results if isinstance(r, AppError) and r.code == "leo_limit"]
    assert (len(results) - len(refused), len(refused)) == (2, 3)
    assert len(await file_bench.leo_events(who)) == 2


async def test_new_files_and_copies_join_leo_by_the_switch_or_the_folder(
    file_bench: FileBench,
) -> None:
    who = person(Home.EU, uuid.uuid4())
    folder = await file_bench.folders.create(who, "Leo")
    await file_bench.folders.update(who, folder.id, name=None, leo=True)
    first = await file_bench.uploaded(who, "Spec.pdf", b"%PDF spec" * 20)
    second = await file_bench.uploaded(who, "Draft.txt", b"draft" * 20)
    picture = await file_bench.uploaded(who, "Photo.png", b"png" * 20)

    [marked] = await file_bench.manager.register(who, [first], None, leo=True)
    [placed] = await file_bench.manager.register(who, [second], folder.id)
    copy_at_root = await file_bench.manager.copy(who, marked.id, None)
    copy_in_folder = await file_bench.manager.copy(who, placed.id, None)
    with pytest.raises(AppError, match="leo_unreadable"):
        await file_bench.manager.register(who, [picture], None, leo=True)

    assert via_of(marked) is LeoVia.FILE
    assert via_of(placed) is LeoVia.FOLDER
    assert copy_at_root.leo is None
    assert via_of(copy_in_folder) is LeoVia.FOLDER
    assert await file_bench.leo_events(who) == [
        (first, True), (second, True), (copy_in_folder.id, True),
    ]  # fmt: skip
    assert (await file_bench.events(who)).count("files.file.uploaded") == 2


async def test_a_reindex_is_asked_only_for_a_file_leo_uses(file_bench: FileBench) -> None:
    who = person(Home.RU, uuid.uuid4())
    ids = await seed(file_bench, who, {"Notes.md": 3 * KB})

    with pytest.raises(AppError, match="leo_not_used"):
        await file_bench.manager.reindex(who, ids["Notes.md"])
    await file_bench.manager.update(who, ids["Notes.md"], FileChanges(leo=True))
    again = await file_bench.manager.reindex(who, ids["Notes.md"])

    assert again.leo is not None
    assert again.leo.state.stage is IndexStage.QUEUED
    assert (await file_bench.events(who))[-1] == "files.leo_use.reindex_requested"


async def test_a_deleted_file_leaves_leo_and_support_s_restore_brings_it_back(
    file_bench: FileBench,
) -> None:
    who = person(Home.EU, uuid.uuid4())
    file_bench.uploads.plan.knowledge_base_mb = 0
    notes = (await seed(file_bench, who, {"Notes.txt": 10 * KB}))["Notes.txt"]
    async with file_bench.uploads.transactions.begin(who.scope()) as session:
        record = await session.get(StorageFileRecord, notes)
        assert record is not None
        record.leo_on = True

    await file_bench.manager.delete(who, notes)
    await file_bench.support.restore(Home.EU, who.user_id, notes)
    _, [restored] = await file_bench.manager.listing(who)

    assert via_of(restored) is LeoVia.FILE
    assert await file_bench.leo_events(who) == [(notes, True)]
    assert await file_bench.events(who) == [
        "files.file.deleted", "files.file.restored", "identity.operator.acted",
        "files.leo_use.changed",
    ]  # fmt: skip


async def test_unknown_entitlements_refuse_a_change_that_may_start_leo(
    file_bench: FileBench,
) -> None:
    who = person(Home.RU, uuid.uuid4())
    notes = (await seed(file_bench, who, {"Notes.txt": 10 * KB}))["Notes.txt"]
    file_bench.uploads.plan.unavailable = True

    with pytest.raises(AppError, match="entitlements_unavailable"):
        await file_bench.manager.update(who, notes, FileChanges(leo=True))
    starred = await file_bench.manager.update(who, notes, FileChanges(starred=True))
    stopped = await file_bench.manager.update(who, notes, FileChanges(leo=False))

    assert (starred.starred, stopped.leo) == (True, None)
