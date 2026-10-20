"""The native import: `POST /v1/me/sessions/import` and `GET /v1/me/sessions/import/{job_id}`.

The shipped clients send the recording as the multipart field `file` and get 202
`{jobId}`, then poll `{id, fileName, stage, progress, meetingId, error}` until the stage is
`ready` or `failed`. The body is read as it arrives (`form_stream.py`); a refusal is
answered once the rest of the body is read, so a client still sending gets it. Ten
imports a minute per person. Errors keep the draft's `detail`: 422
`import_unavailable_no_logs`, 402 `minutes_exhausted`, 422 `unsupported_audio_format`,
422 `empty_file`, 413 `file_too_large`, 404 `import_job_not_found`; a client gone
mid-body leaves nothing behind (400 `request_incomplete`).
"""

from datetime import timedelta
from http import HTTPStatus
from typing import Annotated, Final
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from starlette.requests import ClientDisconnect

from shosai.core.kernel.errors import AppError
from shosai.core.kv.rate_limits import RateLimit, RateLimiter
from shosai.core.ports.directory import PortDirectory
from shosai.core.web.rate_limit import rate_limited
from shosai.features.identity.contracts import Principal, bearer_principal
from shosai.features.meetings.application.import_jobs import ImportJobs
from shosai.features.meetings.application.import_rows import RecordingObject
from shosai.features.meetings.application.native_imports import NativeImports
from shosai.features.meetings.channels.http.form_stream import FormStream
from shosai.features.meetings.channels.http.native_import_texts import failure_text
from shosai.features.meetings.domain.native_import import IMPORT_MAX_BYTES, JobStage

log = structlog.stdlib.get_logger(__name__)
IMPORT_LIMIT: Final = RateLimit("meetings.native_import", 10, timedelta(minutes=1), 10)
# Тело читается не дальше этого: edge пропускает до 32 МБ, поля формы — сверх файла.
BODY_LIMIT: Final = IMPORT_MAX_BYTES + 8 * 1024 * 1024
# Тело запроса черновика: поле формы `file`, его сверяет шлюз D1.
IMPORT_BODY: Final = {
    "required": True,
    "content": {
        "multipart/form-data": {
            "schema": {
                "type": "object",
                "properties": {
                    "file": {"type": "string", "contentMediaType": "application/octet-stream"}
                },
                "required": ["file"],
            }
        }
    },
}


class ImportAccepted(BaseModel):
    """The import's job, to poll."""

    model_config = ConfigDict(validate_by_name=True)

    job_id: str = Field(alias="jobId")


class ImportJobView(BaseModel):
    """An import's job as the 1.4.5 clients decode it."""

    model_config = ConfigDict(validate_by_name=True)

    id: str
    file_name: str = Field(alias="fileName")
    stage: JobStage
    progress: float = Field(ge=0, le=1)
    meeting_id: UUID | None = Field(alias="meetingId")
    error: str | None


def build_native_import_router(
    services: tuple[NativeImports, ImportJobs], ports: PortDirectory, limiter: RateLimiter
) -> APIRouter:
    """The native import and its job."""
    imports, jobs = services
    router = APIRouter(prefix="/v1/me/sessions", tags=["native"])
    signed_in = bearer_principal(ports)

    async def person(principal: Annotated[Principal, Depends(signed_in)]) -> str:
        return str(principal.user_id)

    async def received(principal: Principal, request: Request) -> RecordingObject:
        body = FormStream(request, "file", limit=BODY_LIMIT)
        try:
            await imports.admit(principal)
            part = await body.file()
            filename = imports.named(part.filename)
            recording = await imports.store(principal, filename, body.chunks())
        except AppError:
            await body.drain()
            raise
        await body.drain()
        return recording

    @router.post(
        "/import",
        status_code=HTTPStatus.ACCEPTED,
        dependencies=[Depends(rate_limited(limiter, IMPORT_LIMIT, person))],
        openapi_extra={"requestBody": IMPORT_BODY},
    )
    async def import_my_recording(
        principal: Annotated[Principal, Depends(signed_in)], request: Request
    ) -> ImportAccepted:
        """Send a recording to become a meeting; poll its job."""
        try:
            recording = await received(principal, request)
        except ClientDisconnect:
            # Клиент ушёл посреди тела: загрузка в бакет уже прервана, отвечать некому.
            log.info("Клиент прервал отправку записи", user_id=str(principal.user_id))
            raise AppError("request_incomplete", HTTPStatus.BAD_REQUEST) from None
        run_id = await imports.open(principal, recording)
        return ImportAccepted(job_id=str(run_id))

    @router.get("/import/{job_id}")
    async def get_my_import_job(
        principal: Annotated[Principal, Depends(signed_in)], job_id: UUID
    ) -> ImportJobView:
        """The import's stage, progress, meeting and failure."""
        job = await jobs.job(principal, job_id)
        failed = job.stage is JobStage.FAILED
        return ImportJobView(
            id=str(job.id), file_name=job.file_name, stage=job.stage, progress=job.progress,
            meeting_id=job.meeting_id,
            error=failure_text(job.error_code, job.language) if failed else None,
        )  # fmt: skip

    return router
