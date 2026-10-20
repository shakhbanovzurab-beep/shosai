"""An uploaded recording becomes a meeting (plan step 9a): `POST /v1/meetings/imports`.

The person's ready upload for a recording is claimed from files in the transaction that
creates the meeting — source `import`, ended at its start until intake measures it — and
its `import` run, which points at the claimed object for at most 72 hours. A repeat with
the same upload answers the same meeting and run: files' claim answers the same object,
and the run is unique by `import:{upload}`. A person who keeps no meetings (MT-D6) has
none made. The intake stage is sent after the commit.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from pathlib import PurePosixPath
from typing import Final
from uuid import UUID

import structlog
from pydantic import BaseModel
from sqlalchemy import select

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.ids import new_id
from shosai.core.ports.directory import PortDirectory
from shosai.features.files.contracts import UPLOADS, UploadPurpose
from shosai.features.identity.contracts import Principal
from shosai.features.meetings.application.lifecycle import RunStarter
from shosai.features.meetings.application.run_rows import ensure_run
from shosai.features.meetings.domain.meetings import MeetingSource, MeetingStatus, title_or_default
from shosai.features.meetings.domain.runs import RunSource, Stage, idempotency_key
from shosai.features.meetings.infrastructure.meeting_records import MeetingRecord
from shosai.features.meetings.infrastructure.notes_records import SettingsRecord
from shosai.features.meetings.infrastructure.run_records import RunRecord

# Сколько живёт запись в бакете: правило бакета — страховка, прогон удаляет её сам.
AUDIO_KEPT_FOR: Final = timedelta(hours=72)
log = structlog.stdlib.get_logger(__name__)


class ImportStarted(BaseModel):
    """The meeting an upload became and the run that transcribes it."""

    meeting_id: UUID
    run_id: UUID


class RecordingImports:
    """Turns a person's uploaded recordings into meetings."""

    def __init__(
        self,
        transactions: HomeTransactions,
        collaborators: tuple[PortDirectory, RunStarter],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._ports, self._starter = collaborators
        self._clock = clock

    async def start(self, principal: Principal, upload_id: UUID) -> ImportStarted:
        """The meeting and run of the upload, made once; `upload_not_claimable` otherwise."""
        key = idempotency_key(RunSource.IMPORT, upload_id=upload_id)
        async with self._transactions.begin(principal.scope()) as session:
            claimed = await self._ports.get(UPLOADS).claim(
                session, upload_id, UploadPurpose.RECORDING
            )
            existing = (
                await session.execute(
                    select(RunRecord.session_id, RunRecord.id).where(
                        RunRecord.user_id == principal.user_id, RunRecord.idempotency_key == key
                    )
                )
            ).first()
            if existing is not None:
                return ImportStarted(meeting_id=existing[0], run_id=existing[1])
            settings = await session.get(SettingsRecord, principal.user_id)
            if settings is not None and not settings.keep_meetings:
                raise AppError("meetings_not_kept", HTTPStatus.CONFLICT)
            now = self._clock()
            meeting = MeetingRecord(
                id=new_id(), user_id=principal.user_id,
                title=title_or_default(PurePosixPath(claimed.filename).stem, now),
                status=MeetingStatus.COMPLETED.value, source=MeetingSource.IMPORT.value,
                started_at=now, ended_at=now, seconds=0, created_at=now, updated_at=now,
            )  # fmt: skip
            session.add(meeting)
            await session.flush()
            run_id = await ensure_run(session, meeting, RunSource.IMPORT, key)
            run = await session.get(RunRecord, run_id)
            if run is None:
                message = "прогон импорта не создан"
                raise RuntimeError(message)
            run.audio_key, run.audio_content_type = claimed.object_key, claimed.content_type
            run.audio_size_bytes, run.audio_expires_at = claimed.size_bytes, now + AUDIO_KEPT_FOR
            meeting.latest_run_id = run_id
        await self._starter.kick(principal.scope(), run_id, Stage.INTAKE)
        log.info("Запись принята: встреча создана", meeting_id=str(meeting.id), run_id=str(run_id))
        return ImportStarted(meeting_id=meeting.id, run_id=run_id)
