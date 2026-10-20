"""The library's counts (`GET /v1/notes/counts`): what each person may read, theirs per folder."""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import update

from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.notes.infrastructure.meeting_records import MEETING_RESOURCE, MeetingRecord
from tests.features.notes.library_bench import LibraryBench, MeetingSeed
from tests.features.notes.test_library_isolation import world
from tests.harness.run_slot import RunSlot
from tests.support.access_model import readable

START = datetime.now(UTC).replace(day=1, hour=1, minute=0, second=0, microsecond=0)


@pytest.mark.isolation(resource="meeting")
async def test_every_person_counts_exactly_the_meetings_they_may_read(
    library_bench: LibraryBench, run_slot: RunSlot
) -> None:
    canon = await world(run_slot)

    for name, person in canon.people.items():
        counts = (await library_bench.get(person, "/v1/notes/counts")).json()
        assert counts["all"] == len(readable(canon.world, MEETING_RESOURCE.kind, person)), name


async def test_folders_count_their_owner_s_meetings_still_shown(
    library_bench: LibraryBench,
) -> None:
    owner, stranger = uuid.uuid4(), uuid.uuid4()
    clients, team = await library_bench.folder(owner, "Clients"), await library_bench.folder(owner)
    for folder in (clients, clients, None):
        await library_bench.seed(MeetingSeed(owner, started_at=START, folder_id=folder))
    gone = await library_bench.seed(MeetingSeed(owner, started_at=START, folder_id=team))
    await library_bench.seed(MeetingSeed(stranger, started_at=START))
    scope = TenancyScope(Home.EU, owner)
    async with library_bench.homes.transactions.begin(scope) as session:
        await session.execute(
            update(MeetingRecord)
            .where(MeetingRecord.id == gone.meeting_id)
            .values(deleted_at=START)
        )

    counts = (await library_bench.get(owner, "/v1/notes/counts")).json()
    empty = (await library_bench.get(stranger, "/v1/notes/counts")).json()

    assert counts == {"all": 3, "folders": [{"folder_id": str(clients), "count": 2}]}
    assert empty == {"all": 1, "folders": []}
