"""One order of a person's locks (files): the Leo lock, then the usage row, then the files.

Day 90's removal locks the usage row and then every file of the person; a copy or a
deletion that locked its file before the usage row would wait for the row while the
removal waits for the file — PostgreSQL would break that deadlock by failing one of them.
The test lines both up behind a held usage row in the order that used to deadlock.
"""

import asyncio
import uuid
from collections.abc import Callable, Coroutine
from datetime import timedelta
from typing import Final

import pytest
from sqlalchemy import select

from shosai.core.kernel.homes import Home
from shosai.features.files.domain.quota import GIB, QuotaAction
from shosai.features.files.infrastructure.upload_records import StorageUsageRecord
from shosai.features.identity.contracts import Principal
from tests.features.files.file_bench import FileBench
from tests.features.files.test_quota import seed
from tests.features.files.upload_bench import person
from tests.harness.connections import fetch_value
from tests.harness.run_slot import RunSlot

WAITING_SQL: Final = (
    "SELECT count(*) FROM pg_locks l JOIN pg_stat_activity a ON a.pid = l.pid "
    "WHERE a.datname = current_database() AND NOT l.granted"
)


async def waiting(run_slot: RunSlot, home: Home, count: int) -> None:
    """Return once `count` locks of the slot's database are waited for; fail after 10 s."""
    for _ in range(500):
        waits = await fetch_value(run_slot.claimed.connections[home], WAITING_SQL)
        if isinstance(waits, int) and waits >= count:
            return
        await asyncio.sleep(0.02)
    pytest.fail(f"за 10 с не дождались {count} ожидающих блокировок")


type Contender = Callable[[FileBench, Principal, uuid.UUID], Coroutine[None, None, object]]


async def copy(bench: FileBench, who: Principal, file_id: uuid.UUID) -> object:
    return await bench.manager.copy(who, file_id, None)


async def delete(bench: FileBench, who: Principal, file_id: uuid.UUID) -> object:
    await bench.manager.delete(who, file_id)
    return None


@pytest.mark.parametrize("contender", [copy, delete], ids=["copy", "delete"])
async def test_day_90_s_removal_and_a_person_s_change_never_deadlock(
    file_bench: FileBench, run_slot: RunSlot, contender: Contender
) -> None:
    who = person(Home.RU, uuid.uuid4())
    oldest, _, newest = await seed(file_bench, who, [400 * 1024**2] * 3)
    file_bench.uploads.plan.file_manager_gb = None
    clock = file_bench.uploads.clock
    marked = await file_bench.watch.step(Home.RU, who.user_id, GIB)
    clock.now += timedelta(days=90)

    async with file_bench.uploads.transactions.begin(who.scope()) as holder:
        await holder.execute(
            select(StorageUsageRecord.user_id)
            .where(StorageUsageRecord.user_id == who.user_id)
            .with_for_update()
        )
        removal = asyncio.create_task(file_bench.watch.step(Home.RU, who.user_id, GIB))
        await waiting(run_slot, Home.RU, 1)
        change = asyncio.create_task(contender(file_bench, who, oldest))
        await waiting(run_slot, Home.RU, 2)
    removed, changed = await asyncio.gather(removal, change, return_exceptions=True)
    hidden = {h.file_id for h in await file_bench.support.of_person(Home.RU, who.user_id)}

    assert marked is QuotaAction.MARK
    assert removed is QuotaAction.REMOVE
    assert not isinstance(changed, BaseException), changed
    assert newest in hidden
