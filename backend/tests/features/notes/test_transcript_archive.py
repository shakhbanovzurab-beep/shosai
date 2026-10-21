"""The transcript archive (step 20): a month a year old goes to the bucket, then its partition.

A partition of January 2020 stands for a month long due: the test attaches it as the
migration role, the archiver runs as the workers do, and the partition is gone when the
archive is done, so the catalog ends as it began.
"""

import uuid
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta

from alembic import op
from prometheus_client import CollectorRegistry

from shosai.core.account_data.handlers import AccountRef
from shosai.core.config.roles import ProcessRole
from shosai.core.db.migration_scope import MigrationScope
from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.storage.port import ObjectStorage
from shosai.features.notes.application.account_data import NotesAccountData
from shosai.features.notes.application.live_transcript import LiveTranscript
from shosai.features.notes.application.meeting_reader import MeetingsReader
from shosai.features.notes.application.transcript_archiver import TranscriptArchiver
from shosai.features.notes.contracts import LiveLine, Side
from shosai.features.notes.domain.transcript_archive import archive_key
from shosai.features.notes.infrastructure.archive_metrics import ArchiveMetrics
from shosai.features.notes.infrastructure.meeting_records import (
    MeetingRecord,
    TranscriptLineRecord,
)
from shosai.features.notes.infrastructure.transcript_archive import (
    PartitionDrop,
    TranscriptArchive,
    drop_archived_month,
)
from shosai.features.notes.infrastructure.transcript_metrics import TranscriptMetrics
from shosai.features.workspaces.contracts import Viewer
from tests.core.db.operations import run_step
from tests.core.storage.adapters import slot_storage
from tests.features.notes.library_bench import library_ports
from tests.harness.catalog import CatalogFingerprint
from tests.harness.connections import fetch_rows
from tests.harness.database_access import (
    DatabaseAccess,
    ProcessShape,
    open_database_access,
    slot_urls,
)
from tests.harness.run_slot import RunSlot
from tests.harness.shared_services import SlotBucket

OLD = "transcript_segments_p202001"
STARTED = datetime(2020, 1, 15, 9, tzinfo=UTC)
SAID = [(0, 0, "Hello."), (1, 4000, "Budget first."), (None, 9000, "Agreed.")]


def attach_old_month(_scope: MigrationScope) -> None:
    op.execute(
        f"CREATE TABLE {OLD} PARTITION OF transcript_segments "
        "FOR VALUES FROM ('2020-01-01 00:00+00') TO ('2020-02-01 00:00+00')"
    )


def drop_old_month(_scope: MigrationScope) -> None:
    op.execute(f"DROP TABLE IF EXISTS {OLD}")


@asynccontextmanager
async def old_month(run_slot: RunSlot) -> AsyncIterator[None]:
    """January 2020 in the Russian home for the test; dropped after it if still there."""
    await run_step(run_slot, Home.RU, attach_old_month)
    try:
        yield
    finally:
        await run_step(run_slot, Home.RU, drop_old_month)


async def partitions(run_slot: RunSlot) -> list[str]:
    rows = await fetch_rows(
        run_slot.claimed.connections[Home.RU],
        "SELECT c.relname FROM pg_inherits AS i JOIN pg_class AS c ON c.oid = i.inhrelid "
        "WHERE i.inhparent = 'transcript_segments'::regclass",
    )
    return [row["relname"] for row in rows]


async def seed(
    homes: DatabaseAccess, person: uuid.UUID, said: list[tuple[int | None, int, str]]
) -> uuid.UUID:
    """A meeting of January 2020 with its lines."""
    meeting_id = uuid.uuid4()
    async with homes.transactions.begin(TenancyScope(Home.RU, person)) as session:
        session.add(MeetingRecord(id=meeting_id, user_id=person, title="Q1", started_at=STARTED))
        await session.flush()
        session.add_all(
            TranscriptLineRecord(
                session_id=meeting_id, seq=seq, meeting_started_at=STARTED,
                started_at=STARTED + timedelta(milliseconds=start), start_ms=start,
                duration_ms=900, speaker_idx=speaker, text=text, origin="live",
            )
            for seq, (speaker, start, text) in enumerate(said, 1)
        )  # fmt: skip
    return meeting_id


async def pages(reader: MeetingsReader, person: uuid.UUID, meeting_id: uuid.UUID) -> list[object]:
    """Every page of the meeting's transcript, two lines at a time."""
    found: list[object] = []
    cursor: str | None = None
    while True:
        page = await reader.transcript(Home.RU, Viewer(person), meeting_id, cursor, 2)
        found.append(page.lines)
        if page.next_cursor is None:
            return found
        cursor = page.next_cursor


async def exported(handler: NotesAccountData, account: AccountRef) -> dict[str, bytes]:
    return {
        item.name: b"".join([chunk async for chunk in item.chunks])
        async for item in handler.export(account)
    }


async def pointer(
    transactions: HomeTransactions, home: Home, person: uuid.UUID, meeting_id: uuid.UUID
) -> tuple[str | None, int | None]:
    async with transactions.begin(TenancyScope(home, person), read_only=True) as session:
        meeting = await session.get(MeetingRecord, meeting_id)
    assert meeting is not None
    return meeting.transcript_archive_key, meeting.transcript_archive_lines


async def test_an_archived_meeting_reads_exports_moves_and_erases_as_before(
    homes: DatabaseAccess, run_slot: RunSlot, buckets: Mapping[Home, SlotBucket]
) -> None:
    storages = {home: slot_storage(bucket) for home, bucket in buckets.items()}
    objects: dict[Home, ObjectStorage] = {home: slot.objects for home, slot in storages.items()}
    handler = NotesAccountData(
        homes.transactions, (objects, {home: slot.uploads for home, slot in storages.items()})
    )
    archive, registry = TranscriptArchive(objects), CollectorRegistry()
    reader = MeetingsReader(homes.transactions, library_ports(), archive)
    person = uuid.uuid4()
    russian, european = AccountRef(person, Home.RU), AccountRef(person, Home.EU)
    connection = run_slot.claimed.connections[Home.RU]
    before = await CatalogFingerprint.take(connection)

    async with old_month(run_slot):
        spoken, silent = await seed(homes, person, SAID), await seed(homes, person, [])
        read_before, export_before = (
            await pages(reader, person, spoken),
            await exported(handler, russian),
        )
        shape = ProcessShape(role=ProcessRole.WORKERS)
        async with open_database_access(slot_urls(run_slot), shape) as workers:
            archiver = TranscriptArchiver(workers.transactions, (archive, ArchiveMetrics(registry)))
            archived = await archiver.run(Home.RU)
            again = await archiver.run(Home.RU)
        left = await partitions(run_slot)
        read_after, export_after = (
            await pages(reader, person, spoken),
            await exported(handler, russian),
        )
        stored = [await pointer(homes.transactions, Home.RU, person, m) for m in (spoken, silent)]
        lines = [
            (line.seq, line.text) for line in await archive.lines(Home.RU, archive_key(spoken))
        ]
        await handler.copy(russian, Home.EU)
        same = await handler.manifest(russian) == await handler.manifest(european)
        moved = await pointer(homes.transactions, Home.EU, person, spoken)
        copied = await objects[Home.EU].head(archive_key(spoken))
        await handler.erase(russian)
        await handler.purge(european)
    after = await CatalogFingerprint.take(connection)

    assert (archived, again) == (2, 0)
    assert OLD not in left
    assert stored == [(archive_key(spoken), 3), (archive_key(silent), 0)]
    assert lines == [(1, "Hello."), (2, "Budget first."), (3, "Agreed.")]
    assert read_after == read_before
    assert export_after == export_before
    assert same
    assert moved == (archive_key(spoken), 3)
    assert copied is not None
    for home in Home:
        assert await objects[home].head(archive_key(spoken)) is None
    assert (
        registry.get_sample_value(
            "shosai_notes_transcripts_archived_total", {"home": "ru", "outcome": "archived"}
        )
        == 2
    )
    assert (
        registry.get_sample_value(
            "shosai_notes_transcript_partitions_dropped_total", {"home": "ru"}
        )
        == 1
    )
    assert after.changes_since(before) == []


async def test_a_partition_stays_while_a_meeting_of_it_is_unarchived_and_takes_no_new_lines(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    person = uuid.uuid4()
    drain = LiveTranscript(homes.transactions, TranscriptMetrics(CollectorRegistry()))
    shape = ProcessShape(role=ProcessRole.WORKERS)

    async with old_month(run_slot), open_database_access(slot_urls(run_slot), shape) as workers:
        meeting_id = await seed(homes, person, SAID)
        late = LiveLine(meeting_id, 4, STARTED + timedelta(seconds=20), 700, Side.ME, "Late.")
        outcome = await drain.append(Home.RU, [late])
        async with workers.transactions.begin(TenancyScope(Home.RU), sweep=True) as session:
            kept = await drop_archived_month(session, date(2020, 1, 1))
            absent = await drop_archived_month(session, date(2019, 12, 1))
        left = await partitions(run_slot)

    assert (outcome.stored, outcome.refused) == (0, 1)
    assert (kept, absent) == (PartitionDrop.UNARCHIVED, PartitionDrop.ABSENT)
    assert OLD in left
