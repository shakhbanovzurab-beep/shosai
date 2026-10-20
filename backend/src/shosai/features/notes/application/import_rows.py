"""The meeting and the run of an imported recording, written in the caller's transaction.

Both imports — the cabinet's claim of a files upload (step 9a) and the native body
streamed to the bucket (step 9b) — make the same rows: a meeting of source `import`,
titled by the file's name and ended at its start until intake measures the recording,
and its `import` run pointing at the object for at most 72 hours, unique by
`import:{object}`. A person who keeps no meetings (MT-D6) has none made.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import PurePosixPath
from typing import Final
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.kernel.ids import new_id
from shosai.features.notes.application.run_rows import ensure_run
from shosai.features.notes.domain.meetings import MeetingSource, MeetingStatus, title_or_default
from shosai.features.notes.domain.runs import RunSource, idempotency_key
from shosai.features.notes.infrastructure.meeting_records import MeetingRecord
from shosai.features.notes.infrastructure.notes_records import SettingsRecord
from shosai.features.notes.infrastructure.run_records import RunRecord

# Сколько живёт запись в бакете: правило бакета — страховка, прогон удаляет её сам.
AUDIO_KEPT_FOR: Final = timedelta(hours=72)


class MeetingsNotKeptError(Exception):
    """The person keeps no meetings, so an import makes none."""


@dataclass(frozen=True, slots=True)
class RecordingObject:
    """A recording in the home's bucket, under `transient/`, and the name it came with."""

    object_id: UUID
    object_key: str
    content_type: str
    size_bytes: int
    filename: str


@dataclass(frozen=True, slots=True)
class ImportRows:
    """The meeting and the run an import made, and whether this call made them."""

    meeting_id: UUID
    run_id: UUID
    created: bool


async def existing_import(
    session: AsyncSession, user_id: UUID, object_id: UUID
) -> ImportRows | None:
    """The meeting and run already made for the object, if any."""
    key = idempotency_key(RunSource.IMPORT, upload_id=object_id)
    found = (
        await session.execute(
            select(RunRecord.session_id, RunRecord.id).where(
                RunRecord.user_id == user_id, RunRecord.idempotency_key == key
            )
        )
    ).first()
    return None if found is None else ImportRows(found[0], found[1], created=False)


async def open_import(
    session: AsyncSession, user_id: UUID, recording: RecordingObject, now: datetime
) -> ImportRows:
    """The meeting and run of the recording, made once; `MeetingsNotKeptError` otherwise."""
    existing = await existing_import(session, user_id, recording.object_id)
    if existing is not None:
        return existing
    settings = await session.get(SettingsRecord, user_id)
    if settings is not None and not settings.keep_meetings:
        raise MeetingsNotKeptError
    meeting = MeetingRecord(
        id=new_id(), user_id=user_id,
        title=title_or_default(PurePosixPath(recording.filename).stem, now),
        status=MeetingStatus.COMPLETED.value, source=MeetingSource.IMPORT.value,
        started_at=now, ended_at=now, seconds=0, created_at=now, updated_at=now,
        account_hidden=settings is not None and settings.account_hidden,
    )  # fmt: skip
    session.add(meeting)
    await session.flush()
    key = idempotency_key(RunSource.IMPORT, upload_id=recording.object_id)
    run_id = await ensure_run(session, meeting, RunSource.IMPORT, key)
    run = await session.get(RunRecord, run_id)
    if run is None:
        message = "прогон импорта не создан"
        raise RuntimeError(message)
    run.audio_key, run.audio_content_type = recording.object_key, recording.content_type
    run.audio_size_bytes, run.audio_expires_at = recording.size_bytes, now + AUDIO_KEPT_FOR
    run.source_filename = recording.filename
    meeting.latest_run_id = run_id
    return ImportRows(meeting.id, run_id, created=True)
