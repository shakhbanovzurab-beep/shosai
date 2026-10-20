"""The native import (plan step 9b): `POST /v1/me/sessions/import` admitted, streamed, opened.

The refusals come in the draft's order and before any row: a person who keeps no meetings
(422 `import_unavailable_no_logs`, MT-D6), no minutes left (402 `minutes_exhausted`), a
name off the list (422 `unsupported_audio_format`), an empty file (422 `empty_file`), one
over 25 MiB (413 `file_too_large`). The file goes to the person's home bucket as it
arrives, in parts of 5 MiB, under `transient/import/{id}`; at most sixteen imports stream
at once per process, so memory stays bounded, and one that waits over ten seconds for its
turn is 503 `imports_busy`. The meeting and its run are written once the object is
complete (`import_rows.py`), and the object is deleted when they are not. The intake stage
is sent after the commit; the import's job is its run.
"""

import asyncio
from collections.abc import AsyncIterator, Callable, Mapping
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Final
from uuid import UUID

import structlog

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.homes import Home
from shosai.core.kernel.ids import new_id
from shosai.core.ports.directory import PortDirectory
from shosai.core.storage.errors import StorageRejectedError, StorageUnavailableError
from shosai.core.storage.port import MultipartUpload, MultipartUploads, ObjectStorage, UploadedPart
from shosai.features.billing.contracts import MINUTES_ALLOWANCE
from shosai.features.identity.contracts import Principal
from shosai.features.meetings.application.import_rows import (
    MeetingsNotKeptError,
    RecordingObject,
    open_import,
)
from shosai.features.meetings.application.lifecycle import RunStarter
from shosai.features.meetings.domain.native_import import (
    IMPORT_MAX_BYTES,
    accepted_name,
    media_type_of,
    stored_name,
)
from shosai.features.meetings.domain.runs import Stage
from shosai.features.meetings.infrastructure.notes_records import SettingsRecord

PART_BYTES: Final = 5 * 1024 * 1024
IMPORTS_AT_ONCE: Final = 16
TURN_WAIT_SECONDS: Final = 10.0
NO_LOGS: Final = "import_unavailable_no_logs"
# Сбой бакета при уборке не отменяет ответа: брошенное убирает правило бакета (72 часа).
CLEANUP_FAILURES: Final = (StorageUnavailableError, StorageRejectedError)
log = structlog.stdlib.get_logger(__name__)


class NativeImports:
    """Turns a recording a native client sends into a meeting."""

    def __init__(
        self,
        transactions: HomeTransactions,
        collaborators: tuple[PortDirectory, RunStarter],
        buckets: tuple[Mapping[Home, MultipartUploads], Mapping[Home, ObjectStorage]],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._ports, self._starter = collaborators
        self._uploads, self._objects = buckets
        self._clock = clock
        self._turns = asyncio.Semaphore(IMPORTS_AT_ONCE)

    async def admit(self, principal: Principal) -> None:
        """Refuse a person who keeps no meetings, then one with no minutes left."""
        async with self._transactions.begin(principal.scope()) as session:
            settings = await session.get(SettingsRecord, principal.user_id)
            if settings is not None and not settings.keep_meetings:
                raise AppError(NO_LOGS, HTTPStatus.UNPROCESSABLE_ENTITY)
            await self._ports.get(MINUTES_ALLOWANCE).check(session, principal.user_id, None)

    @staticmethod
    def named(filename: str | None) -> str:
        """The file's name as kept; `unsupported_audio_format` for one off the list."""
        if filename is None or not accepted_name(filename):
            raise AppError("unsupported_audio_format", HTTPStatus.UNPROCESSABLE_ENTITY)
        return stored_name(filename)

    async def store(
        self, principal: Principal, filename: str, chunks: AsyncIterator[bytes]
    ) -> RecordingObject:
        """The file streamed to the person's bucket; `empty_file` or `file_too_large`."""
        try:
            await asyncio.wait_for(self._turns.acquire(), TURN_WAIT_SECONDS)
        except TimeoutError:
            log.warning("Импорт записи не дождался очереди", user_id=str(principal.user_id))
            raise AppError("imports_busy", HTTPStatus.SERVICE_UNAVAILABLE) from None
        try:
            return await self._streamed(principal.home, filename, chunks)
        finally:
            self._turns.release()

    async def open(self, principal: Principal, recording: RecordingObject) -> UUID:
        """The meeting and run of the stored recording; the object goes when they cannot."""
        try:
            async with self._transactions.begin(principal.scope()) as session:
                rows = await open_import(session, principal.user_id, recording, self._clock())
        except MeetingsNotKeptError:
            await self._discard(principal.home, recording.object_key)
            raise AppError(NO_LOGS, HTTPStatus.UNPROCESSABLE_ENTITY) from None
        except BaseException:
            await self._discard(principal.home, recording.object_key)
            raise
        await self._starter.kick(principal.scope(), rows.run_id, Stage.INTAKE)
        log.info(
            "Запись нативного импорта принята",
            meeting_id=str(rows.meeting_id),
            run_id=str(rows.run_id),
            size_bytes=recording.size_bytes,
        )
        return rows.run_id

    async def _streamed(
        self, home: Home, filename: str, chunks: AsyncIterator[bytes]
    ) -> RecordingObject:
        object_id = new_id()
        key, media_type = f"transient/import/{object_id}", media_type_of(filename)
        uploads = self._uploads[home]
        upload: MultipartUpload | None = None
        parts: list[UploadedPart] = []
        pending, size = bytearray(), 0
        try:
            async for chunk in chunks:
                size += len(chunk)
                if size > IMPORT_MAX_BYTES:
                    raise AppError("file_too_large", HTTPStatus.CONTENT_TOO_LARGE)
                pending += chunk
                while len(pending) >= PART_BYTES:
                    upload = upload or await uploads.create(key, content_type=media_type)
                    body = bytes(pending[:PART_BYTES])
                    del pending[:PART_BYTES]
                    parts.append(await uploads.upload_part(upload, len(parts) + 1, body))
            if size == 0:
                raise AppError("empty_file", HTTPStatus.UNPROCESSABLE_ENTITY)
            upload = upload or await uploads.create(key, content_type=media_type)
            if pending or not parts:
                parts.append(await uploads.upload_part(upload, len(parts) + 1, bytes(pending)))
            await uploads.complete(upload, parts)
        except BaseException:
            if upload is not None:
                await self._abandon(uploads, upload)
            raise
        return RecordingObject(object_id, key, media_type, size, filename)

    async def _abandon(self, uploads: MultipartUploads, upload: MultipartUpload) -> None:
        try:
            await uploads.abort(upload)
        except CLEANUP_FAILURES:
            log.warning("Загрузка импорта не прервана: её уберёт правило бакета", exc_info=True)

    async def _discard(self, home: Home, key: str) -> None:
        try:
            await self._objects[home].delete(key)
        except CLEANUP_FAILURES:
            log.warning("Объект импорта не удалён: его уберёт правило бакета", exc_info=True)
