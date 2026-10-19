"""The native rename and deletion of a meeting: `PATCH` and `DELETE /v1/me/sessions/{id}`.

The shipped desktop clients rename a meeting with `{title}` and get `{id, title}` back, and
delete it with 204; both are the owner's, as in the draft. The deletion hides the meeting
for 7 days like the cabinet's (MT-D8). Errors keep the draft's `detail`: 404
`meeting_not_found`, 422 `title_empty`, 403 `meeting_not_yours`, 409 `meeting_active`.
"""

from http import HTTPStatus
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel

from shosai.core.kernel.errors import AppError
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import Principal, bearer_principal
from shosai.features.meetings.application.deletion import MeetingDeletion
from shosai.features.meetings.application.library import MeetingChange, MeetingLibrary
from shosai.features.meetings.domain.meetings import TitleRuleError


class SessionTitleUpdate(BaseModel):
    """A meeting's new title, as the draft's clients send it."""

    title: str


class SessionRenamed(BaseModel):
    """The meeting after its rename, in the draft's shape."""

    id: UUID
    title: str


def build_native_me_sessions_router(
    services: tuple[MeetingLibrary, MeetingDeletion], ports: PortDirectory
) -> APIRouter:
    """The native rename and deletion."""
    library, deletion = services
    router = APIRouter(prefix="/v1/me/sessions", tags=["native"])
    signed_in = bearer_principal(ports)

    @router.patch("/{session_id}")
    async def rename_my_session(
        principal: Annotated[Principal, Depends(signed_in)],
        session_id: UUID,
        body: SessionTitleUpdate,
    ) -> SessionRenamed:
        """Rename the meeting."""
        try:
            view = await library.change(principal, session_id, MeetingChange(title=body.title))
        except TitleRuleError as error:
            raise AppError(error.code, HTTPStatus.UNPROCESSABLE_ENTITY) from error
        return SessionRenamed(id=view.card.meeting_id, title=view.card.title)

    @router.delete("/{session_id}", status_code=HTTPStatus.NO_CONTENT)
    async def delete_my_session(
        principal: Annotated[Principal, Depends(signed_in)], session_id: UUID
    ) -> Response:
        """Delete the meeting: hidden for 7 days, then gone."""
        await deletion.delete(principal, session_id)
        return Response(status_code=HTTPStatus.NO_CONTENT)

    return router
