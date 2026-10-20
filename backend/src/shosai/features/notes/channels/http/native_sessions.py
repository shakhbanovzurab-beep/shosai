"""The native start and end of a meeting: `POST /v1/sessions`, `PATCH /v1/sessions/{id}`.

The shipped desktop clients start a meeting here and end it only with `PATCH` and
`status: completed` — they never send the WebSocket's `session.end` — retrying with a
fresh `ended_at`; every repeat answers the stored meeting. `paused` and `active` change
nothing but the title. Errors keep the draft's `detail`: 402 `minutes_exhausted`, 403
`free_plan_device_taken`, 404 `meeting_not_found`, 422 `title_empty`.
"""

from http import HTTPStatus
from typing import Annotated, Final
from uuid import UUID

from fastapi import APIRouter, Depends

from shosai.core.kernel.errors import AppError
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import Principal, bearer_principal
from shosai.features.notes.application.lifecycle import MeetingLifecycle, MeetingSnapshot
from shosai.features.notes.channels.http.native_models import (
    SessionCreate,
    SessionResponse,
    SessionUpdate,
)
from shosai.features.notes.domain.meetings import MeetingStatus, TitleRuleError

# Конец встречи — только «завершена» и «сломалась»; «идёт» и «на паузе» её не меняют.
ENDING_STATUSES: Final = {
    "completed": MeetingStatus.COMPLETED,
    "failed": MeetingStatus.FAILED,
}


def response_of(meeting: MeetingSnapshot) -> SessionResponse:
    """The draft's answer of a meeting."""
    return SessionResponse(
        id=meeting.meeting_id,
        title=meeting.title,
        started_at=meeting.started_at,
        ended_at=meeting.ended_at,
        status=meeting.status.value,
        client_device_id=meeting.client_device_id or "",
        created_at=meeting.created_at,
        updated_at=meeting.updated_at,
    )


def build_native_sessions_router(lifecycle: MeetingLifecycle, ports: PortDirectory) -> APIRouter:
    """The native meeting start and end."""
    router = APIRouter(prefix="/v1/sessions", tags=["notes"])
    signed_in = bearer_principal(ports)

    @router.post("", status_code=HTTPStatus.CREATED)
    async def create_session(
        principal: Annotated[Principal, Depends(signed_in)], body: SessionCreate
    ) -> SessionResponse:
        """Start a live meeting on this device."""
        meeting = await lifecycle.start(principal, body.title, body.client_device_id)
        return response_of(meeting)

    @router.patch("/{session_id}")
    async def update_session(
        principal: Annotated[Principal, Depends(signed_in)], session_id: UUID, body: SessionUpdate
    ) -> SessionResponse:
        """Retitle the meeting, or end it; a repeated end answers the stored meeting."""
        status = ENDING_STATUSES.get(body.status or "")
        try:
            ended = await lifecycle.update(
                principal, session_id, (body.title, status, body.ended_at)
            )
        except TitleRuleError as error:
            raise AppError(error.code, HTTPStatus.UNPROCESSABLE_ENTITY) from error
        return response_of(ended.meeting)

    return router
