"""Meetings' part of a person's export, transfer and erasure: rows, lines and objects by pointer."""

import uuid
from collections.abc import Mapping
from datetime import UTC, date, datetime

from shosai.core.account_data.handlers import AccountRef
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.meetings.application.account_data import MeetingsAccountData
from shosai.features.meetings.infrastructure.meeting_records import (
    MeetingRecord,
    ParticipantRecord,
    SpeakerRecord,
    TranscriptLineRecord,
)
from shosai.features.meetings.infrastructure.notes_records import (
    FindingRecord,
    FolderRecord,
    NotesRecord,
    SettingsRecord,
    TemplateRecord,
)
from shosai.features.meetings.infrastructure.own_notes_records import OwnNotesRecord
from shosai.features.meetings.infrastructure.run_records import RunRecord
from shosai.features.meetings.infrastructure.share_records import (
    ShareCommentRecord,
    ShareLinkRecord,
)
from tests.core.storage.adapters import slot_storage
from tests.harness.database_access import DatabaseAccess
from tests.harness.shared_services import SlotBucket

STARTED = datetime(2026, 10, 19, 9, tzinfo=UTC)
TOKEN = "secret-link-token"


def meeting_rows(person: uuid.UUID, meeting: uuid.UUID, audio_key: str) -> list[object]:
    """One meeting with everything under it."""
    run = uuid.uuid4()
    return [
        MeetingRecord(id=meeting, user_id=person, title="Созвон", started_at=STARTED),
        *(
            TranscriptLineRecord(
                session_id=meeting,
                seq=seq,
                meeting_started_at=STARTED,
                started_at=STARTED,
                start_ms=seq * 1000,
                duration_ms=900,
                text="Да.",
            )
            for seq in (1, 2)
        ),
        SpeakerRecord(id=uuid.uuid4(), session_id=meeting, user_id=person, idx=0, role="owner"),
        ParticipantRecord(
            id=uuid.uuid4(), session_id=meeting, user_id=person, email="anna@example.com"
        ),
        NotesRecord(session_id=meeting, user_id=person, write_up_template="enhanced"),
        OwnNotesRecord(
            id=uuid.uuid4(),
            session_id=meeting,
            user_id=person,
            markdown="# Мои заметки",
            version=1,
            client="web",
            updated_at=STARTED,
        ),
        FindingRecord(
            id=uuid.uuid4(),
            session_id=meeting,
            user_id=person,
            run_id=run,
            revision=1,
            position=0,
            kind="decision",
            text="Запускаем в пятницу",
            start_ms=1000,
            end_ms=1900,
            due_on=date(2026, 10, 23),
        ),
        RunRecord(
            id=run,
            session_id=meeting,
            user_id=person,
            source="import",
            idempotency_key="import:x",
            audio_key=audio_key,
        ),
        ShareLinkRecord(session_id=meeting, user_id=person, token=TOKEN, allow_comments=True),
    ]


async def test_export_transfer_and_erasure_cover_every_table_and_follow_the_pointers(
    homes: DatabaseAccess, buckets: Mapping[Home, SlotBucket]
) -> None:
    storages = {home: slot_storage(bucket) for home, bucket in buckets.items()}
    objects = {home: storage.objects for home, storage in storages.items()}
    uploads = {home: storage.uploads for home, storage in storages.items()}
    handler = MeetingsAccountData(homes.transactions, (objects, uploads))
    person, meeting = uuid.uuid4(), uuid.uuid4()
    audio_key = f"transient/recording/{uuid.uuid4()}"
    await objects[Home.RU].put(audio_key, b"audio", content_type="audio/mp4")
    async with homes.transactions.begin(TenancyScope(Home.RU, person)) as session:
        session.add_all(
            [
                FolderRecord(id=uuid.uuid4(), user_id=person, name="Клиенты", color="green"),
                TemplateRecord(
                    id=uuid.uuid4(), user_id=person, name="Совет", icon="rocket", sections=[]
                ),
                SettingsRecord(user_id=person, keep_meetings=True),
            ]
        )
        for row in meeting_rows(person, meeting, audio_key):
            session.add(row)
            await session.flush()
        session.add(
            ShareCommentRecord(id=uuid.uuid4(), session_id=meeting, user_id=person, text="Ок")
        )
    # Заметки человека к чужой встрече: выгружаются и стираются с ним, но не переезжают.
    stranger, theirs = uuid.uuid4(), uuid.uuid4()
    async with homes.transactions.begin(TenancyScope(Home.RU, stranger)) as session:
        session.add(MeetingRecord(id=theirs, user_id=stranger, title="Чужая", started_at=STARTED))
    async with homes.transactions.begin(TenancyScope(Home.RU, person)) as session:
        session.add(
            OwnNotesRecord(
                id=uuid.uuid4(), session_id=theirs, user_id=person, markdown="К чужой",
                version=3, client="macos", updated_at=STARTED,
            )
        )  # fmt: skip
    russian, european = AccountRef(person, Home.RU), AccountRef(person, Home.EU)

    exported = {
        item.name: b"".join([chunk async for chunk in item.chunks])
        async for item in handler.export(russian)
    }
    await handler.copy(russian, Home.EU)
    await handler.copy(russian, Home.EU)
    same = await handler.manifest(russian) == await handler.manifest(european)
    copied = await objects[Home.EU].head(audio_key)
    await handler.erase(russian)
    await handler.purge(european)

    assert {
        "sessions.jsonl",
        "transcript_segments.jsonl",
        "meeting_notes.jsonl",
        "meeting_findings.jsonl",
        "meeting_result_shares.jsonl",
        "meeting_share_comments.jsonl",
        "meeting_folders.jsonl",
        "meeting_own_notes.jsonl",
    } <= set(exported)
    assert exported["meeting_own_notes.jsonl"].count(b"\n") == 2
    assert exported["transcript_segments.jsonl"].count(b"\n") == 2
    assert TOKEN.encode() not in exported["meeting_result_shares.jsonl"]
    assert same
    assert copied is not None
    assert await handler.remains(russian) == ()
    assert await handler.remains(european) == ()
    assert await objects[Home.RU].head(audio_key) is None
    assert await objects[Home.EU].head(audio_key) is None
