"""A call's video recording (meetings A7, MR-D4, §3.6)."""

import json
import uuid
from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy import select, update

from shosai.core.config.roles import ProcessRole
from shosai.core.config.sections import StorageSettings
from shosai.core.events.catalog import EventTypes
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.billing.contracts import ENTITLEMENTS
from shosai.features.files.application.written_files import WrittenFilesService
from shosai.features.files.contracts.events import FileUploaded
from shosai.features.files.contracts.written_files import WRITTEN_FILES
from shosai.features.files.infrastructure.file_records import StorageFileRecord
from shosai.features.identity.contracts import Principal as Person
from shosai.features.meetings.application.joining import FoundRoom
from shosai.features.meetings.application.recording import RecordingLimits, Recordings
from shosai.features.meetings.application.video_server import EgressReport, RoomSpec
from shosai.features.meetings.contracts.events import CallEnded, CallStarted, RecordingReady
from shosai.features.meetings.infrastructure.call_records import RoomRecordingRecord
from tests.features.meetings.room_bench import NOW, People, SfuDouble
from tests.features.meetings.room_kit import add_room, room_row
from tests.harness.database_access import (
    DatabaseAccess,
    ProcessShape,
    open_database_access,
    slot_urls,
)
from tests.harness.run_slot import RunSlot


@pytest.fixture
async def workers(run_slot: RunSlot) -> AsyncIterator[DatabaseAccess]:
    async with open_database_access(
        slot_urls(run_slot), ProcessShape(ProcessRole.WORKERS)
    ) as access:
        await access.gate.verify_at_start()
        yield access


BUCKET = StorageSettings.model_validate(
    {
        "s3_endpoint_url": "http://127.0.0.1:18333",
        "s3_region": "local",
        "s3_bucket": "shosai-ru",
        "s3_access_key_id": "local-s3-access",
        "s3_secret_access_key": "local-s3-secret",
    }
)
LIMITS = RecordingLimits(
    concurrent=1,
    length=timedelta(minutes=30),
    buckets={Home.RU: BUCKET},
    endpoints={Home.RU: "http://s3:8333"},
)


def recordings_of(
    homes: DatabaseAccess, sfu: SfuDouble, people: People, limits: RecordingLimits = LIMITS
) -> Recordings:
    """The recordings over the slot's homes, the SFU double and the plan double."""
    ports = PortDirectory()
    outbox = EventOutbox(EventTypes([CallStarted, CallEnded, RecordingReady, FileUploaded]))
    ports.install(
        [
            ENTITLEMENTS.bind(people),
            WRITTEN_FILES.bind(WrittenFilesService(homes.transactions, ports, outbox)),
        ]
    )
    return Recordings(homes.transactions, (sfu, ports, outbox), limits, lambda: NOW)


async def live_room(homes: DatabaseAccess, sfu: SfuDouble, owner: uuid.UUID) -> uuid.UUID:
    """An open room of the owner with a live call, held by the SFU."""
    room = await add_room(homes, room_row(owner))
    async with homes.transactions.begin(TenancyScope(Home.RU, owner)) as session:
        await session.execute(update(RoomRecordingRecord).values(state="complete", ended_at=NOW))
    await sfu.create_room(RoomSpec(room.lk_room_name, 4, "{}"))
    return room.id


def code_of(error: pytest.ExceptionInfo[AppError]) -> tuple[int, str]:
    """The status and code of a refusal."""
    return int(error.value.status), error.value.code


async def test_a_paid_owner_records_into_their_file_key_and_the_file_lands_in_file_manager(
    homes: DatabaseAccess,
) -> None:
    owner, sfu, people = uuid.uuid4(), SfuDouble(), People()
    room_id = await live_room(homes, sfu, owner)
    recordings = recordings_of(homes, sfu, people)
    person = Person(owner, Home.RU, 0)

    record = await recordings.start(person, room_id)
    egress_id, target = next(iter(sfu.targets.items()))
    assert (record.state, target.key) == ("starting", f"u/{owner}/f/{record.id}")
    assert (target.endpoint, target.bucket) == ("http://s3:8333", "shosai-ru")
    assert json.loads(next(iter(sfu.metadata.values())))["marks"]["recording"] is True

    with pytest.raises(AppError) as busy:
        await recordings.start(person, room_id)
    assert code_of(busy) == (409, "recording_active")

    found = FoundRoom(Home.RU, room_id, owner, None)
    report = EgressReport(egress_id, "", "EGRESS_COMPLETE", size_bytes=5_000, duration_seconds=90)
    await recordings.on_report(found, EgressReport(egress_id, "", "EGRESS_ACTIVE"))
    await recordings.on_report(found, report)
    await recordings.on_report(found, EgressReport(egress_id, "", "EGRESS_ACTIVE"))
    await recordings.on_report(found, report)

    async with homes.transactions.begin(TenancyScope(Home.RU, owner), read_only=True) as session:
        row = await session.get_one(RoomRecordingRecord, record.id)
        files = (await session.scalars(select(StorageFileRecord))).all()
    assert (row.state, row.size_bytes, row.duration_seconds, row.file_id) == (
        "complete", 5_000, 90, record.id,
    )  # fmt: skip
    assert [(item.id, item.object_key, item.content_type) for item in files] == [
        (record.id, target.key, "video/mp4")
    ]
    assert json.loads(next(iter(sfu.metadata.values())))["marks"]["recording"] is False


@pytest.mark.parametrize(
    ("setup", "refusal"),
    [
        ({"paid": False}, (403, "recording_not_in_plan")),
        ({"storage_gb": 0}, (413, "storage_limit")),
        ({"busy": True}, (503, "recordings_busy")),
    ],
)
async def test_a_start_is_refused_in_the_domains_order(
    homes: DatabaseAccess, setup: dict[str, Any], refusal: tuple[int, str]
) -> None:
    owner, sfu = uuid.uuid4(), SfuDouble()
    people = People(paid=setup.get("paid", True), file_manager_gb=setup.get("storage_gb"))
    room_id = await live_room(homes, sfu, owner)
    if setup.get("busy"):
        sfu.egress_reports["EG_busy"] = EgressReport("EG_busy", "r-other", "EGRESS_ACTIVE")
    recordings = recordings_of(homes, sfu, people)

    with pytest.raises(AppError) as refused:
        await recordings.start(Person(owner, Home.RU, 0), room_id)

    assert code_of(refused) == refusal


async def test_a_failed_egress_keeps_its_code(
    homes: DatabaseAccess,
) -> None:
    owner, sfu, people = uuid.uuid4(), SfuDouble(), People()
    room_id = await live_room(homes, sfu, owner)
    recordings = recordings_of(homes, sfu, people)
    record = await recordings.start(Person(owner, Home.RU, 0), room_id)
    egress_id = next(iter(sfu.targets))
    found = FoundRoom(Home.RU, room_id, owner, None)

    await recordings.on_report(found, EgressReport(egress_id, "", "EGRESS_ABORTED"))

    async with homes.transactions.begin(TenancyScope(Home.RU, owner), read_only=True) as session:
        row = await session.get_one(RoomRecordingRecord, record.id)
    assert (row.state, row.error_code) == ("failed", "egress_aborted")


async def test_the_sweep_settles_a_lost_webhook_and_stops_a_recording_at_its_limit(
    homes: DatabaseAccess, workers: DatabaseAccess
) -> None:
    owner, sfu, people = uuid.uuid4(), SfuDouble(), People()
    first_room = await live_room(homes, sfu, owner)
    second_room = await live_room(homes, sfu, owner)
    two = replace(LIMITS, concurrent=2)
    recordings = recordings_of(homes, sfu, people, two)
    person = Person(owner, Home.RU, 0)
    lost = await recordings.start(person, first_room)
    long = await recordings.start(person, second_room)
    lost_egress, long_egress = list(sfu.targets)
    sfu.egress_reports[lost_egress] = EgressReport(
        lost_egress, "", "EGRESS_COMPLETE", size_bytes=10, duration_seconds=5
    )
    async with homes.transactions.begin(TenancyScope(Home.RU, owner)) as session:
        await session.execute(
            update(RoomRecordingRecord)
            .where(RoomRecordingRecord.id == lost.id)
            .values(started_at=NOW - timedelta(minutes=3))
        )
        await session.execute(
            update(RoomRecordingRecord)
            .where(RoomRecordingRecord.id == long.id)
            .values(started_at=NOW - timedelta(minutes=31))
        )

    await recordings_of(workers, sfu, people, two).reconcile(Home.RU, NOW)

    async with homes.transactions.begin(TenancyScope(Home.RU, owner), read_only=True) as session:
        settled = await session.get_one(RoomRecordingRecord, lost.id)
    assert (settled.state, settled.file_id) == ("complete", lost.id)
    assert sfu.egress_reports[long_egress].status == "EGRESS_ENDING"
