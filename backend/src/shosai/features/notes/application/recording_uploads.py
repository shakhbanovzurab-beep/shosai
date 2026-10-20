"""A desktop recording sent in parts (plan step 11, MT-D3): begin, parts, state, complete.

`init` is the meeting owner's, on a live meeting that is kept (409 `private_meeting` for
one that is not), and idempotent: the meeting's one `recording` run answers with the
upload it has open, a new one when it has none or its upload is gone, or `completed` when
its audio is bound. The run waits — the recovery sweep passes it by — until its audio is
bound and its meeting has ended. A part streams to its presigned link; the state is the
bucket's list of parts. `complete` assembles the object, binds it to the run and commits
before it answers: the receipt lets the client delete its copy. The intake goes after the
commit when the meeting has ended, else the recovery sweep sends it once it ends.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from http import HTTPStatus
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.core.storage.errors import ObjectNotFoundError
from shosai.core.storage.port import MultipartUpload, MultipartUploads, ObjectStorage
from shosai.features.identity.contracts import Principal
from shosai.features.notes.application.import_rows import AUDIO_KEPT_FOR
from shosai.features.notes.application.lifecycle import RunStarter
from shosai.features.notes.application.run_rows import ensure_run
from shosai.features.notes.application.visibility import meeting_scope
from shosai.features.notes.contracts import MeetingNotFoundError
from shosai.features.notes.domain.meetings import PRIVATE_MEETING, MeetingSource, MeetingStatus
from shosai.features.notes.domain.recording_upload import (
    NO_PARTS,
    NO_UPLOAD,
    UploadState,
    object_key,
    part_refusal,
)
from shosai.features.notes.domain.runs import RunSource, Stage, idempotency_key
from shosai.features.notes.infrastructure.meeting_records import MeetingRecord
from shosai.features.notes.infrastructure.part_links import PartBody, PartLinks
from shosai.features.notes.infrastructure.run_records import RunRecord
from shosai.features.workspaces.contracts import ACCESS_POLICY

log = structlog.stdlib.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class UploadRequest:
    """What the client says of the file before its bytes: name, type, how early it began."""

    filename: str
    mimetype: str
    lead_ms: int | None


def bound(run: RunRecord) -> bool:
    """Whether the run's recording is assembled and bound to it."""
    return run.multipart_id is None and run.audio_expires_at is not None


def receipt(run: RunRecord) -> UploadState:
    """The state of a bound recording: complete, its size the object's."""
    return UploadState(run.id, "", bytes_received=run.audio_size_bytes or 0, completed=True)


class RecordingUploads:
    """The desktop clients' resumable upload of a meeting's recording."""

    def __init__(
        self,
        transactions: HomeTransactions,
        collaborators: tuple[PortDirectory, RunStarter, PartLinks],
        buckets: tuple[Mapping[Home, MultipartUploads], Mapping[Home, ObjectStorage]],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._ports, self._starter, self._links = collaborators
        self._uploads, self._objects = buckets
        self._clock = clock

    async def begin(
        self, principal: Principal, meeting_id: UUID, request: UploadRequest
    ) -> UploadState:
        """The meeting's upload, begun once; its state when it is already under way."""
        scope = await self._scope(principal, meeting_id)
        uploads = self._uploads[scope.home]
        async with self._transactions.begin(scope) as session:
            meeting = await self._owned(session, principal, meeting_id)
            if not meeting.kept:
                raise AppError(PRIVATE_MEETING, HTTPStatus.CONFLICT)
            key = idempotency_key(RunSource.RECORDING)
            run_id = await ensure_run(session, meeting, RunSource.RECORDING, key)
            run = await session.get(RunRecord, run_id, with_for_update=True)
            if run is None:
                raise MeetingNotFoundError
            if bound(run):
                return receipt(run)
            if run.multipart_id is not None and run.audio_key is not None:
                found = await self._listed(uploads, run.id, run.audio_key, run.multipart_id)
                if found is not None:
                    return found
            upload = await uploads.create(object_key(run.id), content_type=request.mimetype)
            run.audio_key, run.multipart_id = upload.key, upload.upload_id
            run.audio_content_type, run.audio_lead_ms = request.mimetype, request.lead_ms
            run.updated_at = self._clock()
        log.info("Загрузка записи начата", run_id=str(run_id), lead_ms=request.lead_ms)
        return UploadState(run_id, upload.upload_id)

    async def state(self, principal: Principal, meeting_id: UUID, run_id: UUID) -> UploadState:
        """What the bucket has of the upload."""
        scope, run = await self._run(principal, meeting_id, run_id)
        if bound(run):
            return receipt(run)
        if run.multipart_id is None or run.audio_key is None:
            return UploadState(run.id, "")
        found = await self._listed(
            self._uploads[scope.home], run.id, run.audio_key, run.multipart_id
        )
        if found is None:
            raise AppError(NO_UPLOAD, HTTPStatus.CONFLICT)
        return found

    async def part(
        self, principal: Principal, ids: tuple[UUID, UUID], number: int, body: tuple[int, PartBody]
    ) -> UploadState:
        """Send one part on to the bucket; a repeat of its number replaces it."""
        length, content = body
        scope, run = await self._run(principal, *ids)
        if bound(run) or run.multipart_id is None or run.audio_key is None:
            raise AppError(NO_UPLOAD, HTTPStatus.CONFLICT)
        refusal = part_refusal(number, length)
        if refusal is not None:
            raise AppError(refusal, HTTPStatus.CONFLICT)
        uploads = self._uploads[scope.home]
        upload = MultipartUpload(run.audio_key, run.multipart_id)
        link = await uploads.presign_part(upload, number, content_length=length)
        await self._links.send(link, content)
        found = await self._listed(uploads, run.id, run.audio_key, run.multipart_id)
        if found is None:
            raise AppError(NO_UPLOAD, HTTPStatus.CONFLICT)
        return found

    async def complete(self, principal: Principal, meeting_id: UUID, run_id: UUID) -> UploadState:
        """Assemble and bind the recording; the receipt only after the commit."""
        scope = await self._scope(principal, meeting_id)
        async with self._transactions.begin(scope) as session:
            run = await self._owned_run(session, principal, (meeting_id, run_id), lock=True)
            if bound(run):
                return receipt(run)
            if run.multipart_id is None or run.audio_key is None:
                raise AppError(NO_UPLOAD, HTTPStatus.CONFLICT)
            size = await self._assembled(
                scope.home, MultipartUpload(run.audio_key, run.multipart_id)
            )
            now = self._clock()
            run.multipart_id, run.audio_size_bytes = None, size
            run.audio_expires_at, run.updated_at = now + AUDIO_KEPT_FOR, now
            meeting = await session.get(MeetingRecord, meeting_id, with_for_update=True)
            if meeting is None:
                raise MeetingNotFoundError
            meeting.latest_run_id = run.id
            ended = meeting.status != MeetingStatus.ACTIVE.value
        if ended:
            await self._starter.kick(scope, run_id, Stage.INTAKE)
        log.info("Запись встречи принята", run_id=str(run_id), size_bytes=size, ended=ended)
        return UploadState(run_id, "", bytes_received=size, completed=True)

    async def discard(self, principal: Principal, meeting_id: UUID, run_id: UUID) -> None:
        """Drop the upload under way and its parts; a bound recording stays."""
        scope = await self._scope(principal, meeting_id)
        async with self._transactions.begin(scope) as session:
            run = await self._owned_run(session, principal, (meeting_id, run_id), lock=True)
            if bound(run):
                return
            if run.multipart_id is not None and run.audio_key is not None:
                upload = MultipartUpload(run.audio_key, run.multipart_id)
                await self._uploads[scope.home].abort(upload)
            run.multipart_id = run.audio_key = run.audio_content_type = None
            run.updated_at = self._clock()
        log.info("Загрузка записи брошена", run_id=str(run_id))

    async def _assembled(self, home: Home, upload: MultipartUpload) -> int:
        """The object's size once assembled; one assembled before its commit was lost counts."""
        try:
            parts = await self._uploads[home].list_parts(upload)
        except ObjectNotFoundError:
            parts = None
        if parts is not None:
            if not parts:
                raise AppError(NO_PARTS, HTTPStatus.CONFLICT)
            await self._uploads[home].complete(upload, parts)
        info = await self._objects[home].head(upload.key)
        if info is None:
            raise AppError(NO_UPLOAD, HTTPStatus.CONFLICT)
        return info.size

    async def _listed(
        self, uploads: MultipartUploads, run_id: UUID, key: str, upload_id: str
    ) -> UploadState | None:
        """The upload's state from the bucket's list of parts; None when the upload is gone."""
        try:
            parts = await uploads.list_parts(MultipartUpload(key, upload_id))
        except ObjectNotFoundError:
            return None
        return UploadState(
            run_id, upload_id, received=tuple(part.number for part in parts),
            bytes_received=sum(part.size for part in parts),
        )  # fmt: skip

    async def _scope(self, principal: Principal, meeting_id: UUID) -> TenancyScope:
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            return await meeting_scope(
                session, self._ports.get(ACCESS_POLICY), principal.scope(), meeting_id
            )

    async def _owned(
        self, session: AsyncSession, principal: Principal, meeting_id: UUID
    ) -> MeetingRecord:
        """The person's own live meeting, locked; `meeting_not_found` for any other."""
        meeting = await session.scalar(
            select(MeetingRecord)
            .where(
                MeetingRecord.id == meeting_id, MeetingRecord.user_id == principal.user_id,
                MeetingRecord.source == MeetingSource.LIVE.value,
                MeetingRecord.deleted_at.is_(None),
            )
            .with_for_update()
        )  # fmt: skip
        if meeting is None:
            raise MeetingNotFoundError
        return meeting

    async def _run(
        self, principal: Principal, meeting_id: UUID, run_id: UUID
    ) -> tuple[TenancyScope, RunRecord]:
        scope = await self._scope(principal, meeting_id)
        async with self._transactions.begin(scope, read_only=True) as session:
            run = await self._owned_run(session, principal, (meeting_id, run_id), lock=False)
        return scope, run

    async def _owned_run(
        self, session: AsyncSession, principal: Principal, ids: tuple[UUID, UUID], *, lock: bool
    ) -> RunRecord:
        """The person's recording run of the meeting; `upload_not_found` for any other."""
        meeting_id, run_id = ids
        statement = select(RunRecord).where(
            RunRecord.id == run_id, RunRecord.session_id == meeting_id,
            RunRecord.user_id == principal.user_id,
            RunRecord.source == RunSource.RECORDING.value,
        )  # fmt: skip
        run = await session.scalar(statement.with_for_update() if lock else statement)
        if run is None:
            raise AppError("upload_not_found", HTTPStatus.NOT_FOUND)
        return run
