"""An uploaded recording becomes a meeting (plan step 9a): `POST /v1/meetings/imports`.

The person's ready upload for a recording is claimed from files in the transaction that
creates the meeting and its `import` run (`import_rows.py`). A repeat with the same
upload answers the same meeting and run: files' claim answers the same object, and the
run is unique by `import:{upload}`. A person who keeps no meetings (MT-D6) is refused
with 409 `meetings_not_kept` and the upload stays ready. The intake stage is sent after
the commit.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from http import HTTPStatus
from uuid import UUID

import structlog
from pydantic import BaseModel

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.errors import AppError
from shosai.core.ports.directory import PortDirectory
from shosai.features.files.contracts import UPLOADS, UploadPurpose
from shosai.features.identity.contracts import Principal
from shosai.features.meetings.application.import_rows import (
    MeetingsNotKeptError,
    RecordingObject,
    open_import,
)
from shosai.features.meetings.application.lifecycle import RunStarter
from shosai.features.meetings.domain.runs import Stage

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
        async with self._transactions.begin(principal.scope()) as session:
            claimed = await self._ports.get(UPLOADS).claim(
                session, upload_id, UploadPurpose.RECORDING
            )
            recording = RecordingObject(
                object_id=claimed.upload_id, object_key=claimed.object_key,
                content_type=claimed.content_type, size_bytes=claimed.size_bytes,
                filename=claimed.filename,
            )  # fmt: skip
            try:
                rows = await open_import(session, principal.user_id, recording, self._clock())
            except MeetingsNotKeptError:
                raise AppError("meetings_not_kept", HTTPStatus.CONFLICT) from None
        if rows.created:
            await self._starter.kick(principal.scope(), rows.run_id, Stage.INTAKE)
            log.info(
                "Запись принята: встреча создана",
                meeting_id=str(rows.meeting_id),
                run_id=str(rows.run_id),
            )
        return ImportStarted(meeting_id=rows.meeting_id, run_id=rows.run_id)
