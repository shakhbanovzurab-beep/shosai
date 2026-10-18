"""FL-D10 (files step 6b): 90 days over the knowledge limit with three reminders, then Leo
stops using the newest files over it; nothing is deleted and the person chooses again.
"""

import asyncio
import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Final

import pytest
from sqlalchemy.dialects.postgresql import insert

from shosai.core.config.roles import ProcessRole
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.homes import Home
from shosai.features.files.application.file_manager import FileChanges
from shosai.features.files.application.leo_sweep import LeoSweep
from shosai.features.files.domain.quota import QuotaAction
from shosai.features.files.infrastructure.file_records import FileFolderRecord, StorageFileRecord
from shosai.features.files.infrastructure.upload_records import StorageUsageRecord
from shosai.features.identity.contracts import Principal
from tests.features.files.file_bench import FileBench
from tests.features.files.upload_bench import person
from tests.harness.connections import fetch_value
from tests.harness.database_access import ProcessShape, open_database_access, slot_urls
from tests.harness.run_slot import RunSlot

KB: Final = 1000
REMINDER_COUNT_SQL: Final = (
    "SELECT count(*) FROM email_messages WHERE template = 'files.leo_over_limit'"
)


@dataclass(frozen=True, slots=True)
class Seeded:
    """A file to seed: its name, size, own switch and whether it sits in the Leo folder."""

    name: str
    size: int
    own: bool = True
    in_folder: bool = False


async def seed(bench: FileBench, who: Principal, files: list[Seeded]) -> list[uuid.UUID]:
    """The files, oldest first, a folder Leo reads, and the counter that sums them."""
    ids = [uuid.uuid4() for _ in files]
    start = bench.uploads.clock.now - timedelta(days=30)
    folder_id = uuid.uuid4()
    async with bench.uploads.transactions.begin(who.scope()) as session:
        session.add(FileFolderRecord(id=folder_id, user_id=who.user_id, name="Leo", leo=True))
        await session.flush()
        for number, (file_id, item) in enumerate(zip(ids, files, strict=True)):
            moment = start + timedelta(minutes=number)
            session.add(
                StorageFileRecord(
                    id=file_id, user_id=who.user_id, name=item.name, content_type="text/plain",
                    size_bytes=item.size, object_key=f"u/{who.user_id}/f/{file_id}",
                    leo_on=item.own, folder_id=folder_id if item.in_folder else None,
                    created_at=moment, modified_at=moment,
                )
            )  # fmt: skip
        await session.execute(
            insert(StorageUsageRecord).values(
                user_id=who.user_id, used_bytes=sum(item.size for item in files)
            )
        )
    return ids


async def sweep(bench: FileBench, run_slot: RunSlot, home: Home) -> int:
    """The daily knowledge pass as the workers run it."""
    async with open_database_access(
        slot_urls(run_slot), ProcessShape(role=ProcessRole.WORKERS)
    ) as workers:
        return await LeoSweep(workers.transactions, bench.leo_watch, bench.uploads.clock).run(home)


async def reminders(run_slot: RunSlot, home: Home) -> int:
    count = await fetch_value(run_slot.claimed.connections[home], REMINDER_COUNT_SQL)
    assert isinstance(count, int)
    return count


async def in_use(bench: FileBench, who: Principal) -> set[uuid.UUID]:
    _, files = await bench.manager.listing(who)
    return {view.id for view in files if view.leo is not None}


async def test_over_the_knowledge_limit_nothing_stops_for_90_days_and_each_reminder_goes_once(
    file_bench: FileBench, run_slot: RunSlot
) -> None:
    who = person(Home.RU, uuid.uuid4())
    parts = [Seeded(f"Part {n}.txt", 400 * KB) for n in range(3)]
    *ids, extra = await seed(file_bench, who, [*parts, Seeded("Extra.txt", 10 * KB, own=False)])
    file_bench.uploads.plan.knowledge_base_mb = 1
    clock = file_bench.uploads.clock
    start = clock.now

    marked = await sweep(file_bench, run_slot, Home.RU)
    standing = await file_bench.leo_watch.standing(Home.RU, who.user_id)
    counted: list[int] = []
    for day in (59, 60, 60, 83, 89):
        clock.now = start + timedelta(days=day)
        await sweep(file_bench, run_slot, Home.RU)
        counted.append(await reminders(run_slot, Home.RU))
    with pytest.raises(AppError, match="leo_limit"):
        await file_bench.manager.update(who, extra, FileChanges(leo=True))

    assert marked == 1
    assert (standing.used_bytes, standing.limit_bytes) == (1200 * KB, 1024**2)
    assert (standing.over_limit_since, standing.removal_at) == (start, start + timedelta(days=90))
    assert counted == [0, 1, 1, 2, 3]
    assert await in_use(file_bench, who) == set(ids)
    assert await file_bench.leo_events(who) == []


async def test_on_day_90_exactly_the_newest_files_over_the_limit_stop_and_stay_in_my_files(
    file_bench: FileBench, run_slot: RunSlot
) -> None:
    who = person(Home.EU, uuid.uuid4())
    oldest, middle, newest = await seed(
        file_bench, who,
        [Seeded("Old.txt", 900 * KB), Seeded("Mid.md", 200 * KB, own=False, in_folder=True),
         Seeded("New.txt", 200 * KB)],
    )  # fmt: skip
    file_bench.uploads.plan.knowledge_base_mb = 1
    clock = file_bench.uploads.clock
    start = clock.now
    await sweep(file_bench, run_slot, Home.EU)

    clock.now = start + timedelta(days=90)
    await sweep(file_bench, run_slot, Home.EU)
    used_after = await in_use(file_bench, who)
    standing = await file_bench.leo_watch.standing(Home.EU, who.user_id)
    _, files = await file_bench.manager.listing(who)
    await file_bench.manager.update(who, oldest, FileChanges(leo=False))
    chosen = await file_bench.manager.update(who, middle, FileChanges(leo=True))

    assert used_after == {oldest}
    assert {view.id for view in files} == {oldest, middle, newest}
    assert (standing.used_bytes, standing.over_limit_since) == (900 * KB, None)
    assert chosen.leo is not None
    events = await file_bench.leo_events(who)
    assert set(events[:2]) == {(middle, False), (newest, False)}
    assert events[2:] == [(oldest, False), (middle, True)]


async def test_a_held_file_stays_out_of_its_folder_until_the_person_switches_it_on(
    file_bench: FileBench, run_slot: RunSlot
) -> None:
    who = person(Home.RU, uuid.uuid4())
    kept, held = await seed(
        file_bench, who,
        [Seeded("Kept.txt", 900 * KB), Seeded("Held.md", 300 * KB, own=False, in_folder=True)],
    )  # fmt: skip
    file_bench.uploads.plan.knowledge_base_mb = 1
    clock = file_bench.uploads.clock
    start = clock.now
    await sweep(file_bench, run_slot, Home.RU)
    clock.now = start + timedelta(days=90)
    await sweep(file_bench, run_slot, Home.RU)

    file_bench.uploads.plan.knowledge_base_mb = 100
    await file_bench.manager.update(who, held, FileChanges(name="Held v2.md"))
    still_held = await in_use(file_bench, who)
    await file_bench.manager.update(who, held, FileChanges(leo=True))

    assert still_held == {kept}
    assert await in_use(file_bench, who) == {kept, held}


async def test_back_under_the_limit_the_mark_clears_and_a_plan_change_or_restore_marks_at_once(
    file_bench: FileBench, run_slot: RunSlot
) -> None:
    who = person(Home.EU, uuid.uuid4())
    first, second = await seed(
        file_bench, who, [Seeded("First.txt", 600 * KB), Seeded("Second.txt", 600 * KB)]
    )
    file_bench.uploads.plan.knowledge_base_mb = 1
    watch = file_bench.leo_watch
    limit = await watch.limit(Home.EU, who.user_id)
    async with file_bench.uploads.transactions.begin(who.scope()) as session:
        followed = await watch.follow(session, who.user_id, limit)

    await file_bench.manager.update(who, second, FileChanges(leo=False))
    cleared = await sweep(file_bench, run_slot, Home.EU)
    after_clear = await watch.standing(Home.EU, who.user_id)
    await file_bench.manager.delete(who, first)
    await file_bench.manager.update(who, second, FileChanges(leo=True))
    await file_bench.hidden.restore(Home.EU, who.user_id, first)
    restored = await watch.standing(Home.EU, who.user_id)

    assert followed is QuotaAction.MARK
    assert (cleared, after_clear.over_limit_since) == (1, None)
    assert restored.over_limit_since == file_bench.uploads.clock.now
    assert restored.used_bytes == 1200 * KB


async def test_day_90_and_a_person_s_switch_at_once_never_pass_the_limit_or_deadlock(
    file_bench: FileBench, run_slot: RunSlot
) -> None:
    who = person(Home.RU, uuid.uuid4())
    files = [Seeded("Old.txt", 900 * KB), Seeded("New.txt", 300 * KB)]
    *_, idle = await seed(file_bench, who, [*files, Seeded("Idle.txt", 50 * KB, own=False)])
    file_bench.uploads.plan.knowledge_base_mb = 1
    limit = 1024**2
    clock = file_bench.uploads.clock
    start = clock.now
    await sweep(file_bench, run_slot, Home.RU)
    clock.now = start + timedelta(days=90)

    removed, switched = await asyncio.gather(
        file_bench.leo_watch.step(Home.RU, who.user_id, limit),
        file_bench.manager.update(who, idle, FileChanges(leo=True)),
        return_exceptions=True,
    )
    standing = await file_bench.leo_watch.standing(Home.RU, who.user_id)

    assert removed is QuotaAction.REMOVE
    assert not isinstance(switched, BaseException) or (
        isinstance(switched, AppError) and switched.code == "leo_limit"
    ), switched
    assert standing.used_bytes <= limit
