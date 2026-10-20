"""The desktop recording's upload: `/v1/me/sessions/{session_id}/audio/…` (plan step 11).

The shipped macOS and Windows clients begin with `init` (idempotent, it is how they resume),
send the parts the server does not have — raw bodies of the part size it gives — complete,
and delete their copy once the receipt says the bytes received equal their file. `DELETE`
drops an upload under way; a 404 means the same to them. Errors keep the draft's `detail`
code: 409 `private_meeting`, `no_upload`, `no_parts`, `bad_part`, `empty_part`; 413
`part_too_large`; 404 `meeting_not_found`, `upload_not_found`. A refused part's body is
read to its end first, so a client still sending gets the answer; a client gone mid-part
is 400 `request_incomplete`, and the bucket keeps no half of it.
"""

from http import HTTPStatus
from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Path, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from starlette.requests import ClientDisconnect

from shosai.core.kernel.errors import AppError
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import Principal, bearer_principal
from shosai.features.meetings.application.recording_uploads import RecordingUploads, UploadRequest
from shosai.features.meetings.domain.recording_upload import (
    FILENAME_MAX,
    LEAD_MAX_MS,
    MAX_PART_BYTES,
    PART_TOO_LARGE,
    UploadState,
)
from shosai.features.meetings.infrastructure.part_links import PartBody

log = structlog.stdlib.get_logger(__name__)


class UploadInit(BaseModel):
    """What the desktop says of the file before its bytes; unknown fields are accepted."""

    model_config = ConfigDict(extra="ignore")

    filename: Annotated[str, Field(min_length=1, max_length=FILENAME_MAX)]
    mimetype: Annotated[str, Field(max_length=128)] = "audio/wav"
    # Насколько раньше встречи началась запись; клиенты меряют его монотонными часами.
    audio_lead_ms: int | None = None


class UploadStateOut(BaseModel):
    """The upload's state, from which the desktop decides what to send next."""

    run_id: UUID
    upload_id: str
    part_size: int
    received: list[int]
    bytes_received: int
    completed: bool


def state_out(state: UploadState) -> UploadStateOut:
    """The draft's shape of the state."""
    return UploadStateOut(
        run_id=state.run_id, upload_id=state.upload_id, part_size=state.part_size,
        received=list(state.received), bytes_received=state.bytes_received,
        completed=state.completed,
    )  # fmt: skip


async def drained(content: PartBody) -> None:
    """Read what is left of a refused part's body, up to a part's limit, and drop it."""
    if isinstance(content, bytes):
        return
    read = 0
    async for chunk in content:
        read += len(chunk)
        if read > MAX_PART_BYTES:
            return


async def part_body(request: Request) -> tuple[int, PartBody]:
    """The part's length and its body: streamed when its length is declared, else read."""
    declared = request.headers.get("content-length")
    if declared is not None and declared.isdigit():
        length = int(declared)
        if length > MAX_PART_BYTES:
            raise AppError(PART_TOO_LARGE, HTTPStatus.CONTENT_TOO_LARGE)
        return length, request.stream()
    body = bytearray()
    async for chunk in request.stream():
        body += chunk
        if len(body) > MAX_PART_BYTES:
            raise AppError(PART_TOO_LARGE, HTTPStatus.CONTENT_TOO_LARGE)
    return len(body), bytes(body)


def build_native_audio_router(uploads: RecordingUploads, ports: PortDirectory) -> APIRouter:
    """The desktop recording's upload."""
    router = APIRouter(prefix="/v1/me/sessions/{session_id}/audio", tags=["native"])
    signed_in = bearer_principal(ports)

    @router.post("/init")
    async def init_audio_upload(
        principal: Annotated[Principal, Depends(signed_in)], session_id: UUID, body: UploadInit
    ) -> UploadStateOut:
        """Begin the meeting's recording upload, or find where it stopped."""
        # Поле черновик не читал: странное значение не отказ, а прижимается к 6 часам.
        lead = body.audio_lead_ms
        if lead is not None:
            lead = max(-LEAD_MAX_MS, min(LEAD_MAX_MS, lead))
        request = UploadRequest(body.filename, body.mimetype, lead)
        return state_out(await uploads.begin(principal, session_id, request))

    @router.put("/{run_id}/part/{number}")
    async def upload_audio_part(
        principal: Annotated[Principal, Depends(signed_in)],
        session_id: UUID,
        run_id: UUID,
        number: Annotated[int, Path(ge=1)],
        request: Request,
    ) -> UploadStateOut:
        """Send one part; sending a number again replaces it."""
        try:
            body = await part_body(request)
            try:
                state = await uploads.part(principal, (session_id, run_id), number, body)
            except AppError:
                await drained(body[1])
                raise
        except ClientDisconnect:
            # Клиент ушёл посреди части: бакет её не собрал, клиент пришлёт её снова.
            log.info("Клиент прервал отправку части записи", run_id=str(run_id), part=number)
            raise AppError("request_incomplete", HTTPStatus.BAD_REQUEST) from None
        return state_out(state)

    @router.get("/{run_id}")
    async def audio_upload_state(
        principal: Annotated[Principal, Depends(signed_in)], session_id: UUID, run_id: UUID
    ) -> UploadStateOut:
        """How much of the recording the bucket has."""
        return state_out(await uploads.state(principal, session_id, run_id))

    @router.post("/{run_id}/complete")
    async def complete_audio_upload(
        principal: Annotated[Principal, Depends(signed_in)], session_id: UUID, run_id: UUID
    ) -> UploadStateOut:
        """Assemble the recording; the answer is the receipt to delete the local copy."""
        return state_out(await uploads.complete(principal, session_id, run_id))

    @router.delete("/{run_id}", status_code=HTTPStatus.NO_CONTENT)
    async def discard_audio_upload(
        principal: Annotated[Principal, Depends(signed_in)], session_id: UUID, run_id: UUID
    ) -> Response:
        """Drop the upload under way and its parts."""
        await uploads.discard(principal, session_id, run_id)
        return Response(status_code=HTTPStatus.NO_CONTENT)

    return router
