"""The cabinet's library: `GET /v1/meetings`, `GET` and `PATCH /v1/meetings/{id}` (step 7a).

The library lists every meeting the person may read, newest first, in cursor pages; it
narrows to one of their folders (`folder=<id>`), to their meetings in no folder
(`folder=none`), or to a workspace. A meeting's page adds its participants, speakers and
the state of its notes. `PATCH` renames the meeting (whoever may manage it) or files it
(its owner, a personal meeting) or chooses its template; `DELETE` hides the owner's meeting
for 7 days (MT-D8). Errors: `meeting_not_found`, `meeting_not_yours`, `meeting_active`,
`meeting_read_only`, `title_empty`, `folder_not_found`, `meeting_not_yours`,
`company_meeting_has_no_folder`, `template_not_found`, `template_not_shipped`,
`invalid_cursor`.
"""

from http import HTTPStatus
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response

from shosai.core.kernel.errors import AppError
from shosai.core.pagination.page import Page, PageParameters
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import Principal, bearer_principal
from shosai.features.meetings.application.deletion import MeetingDeletion
from shosai.features.meetings.application.library import (
    LibraryFilter,
    MeetingChange,
    MeetingLibrary,
)
from shosai.features.meetings.channels.http.meeting_models import (
    MeetingCardOut,
    MeetingChangeIn,
    MeetingOut,
    card_out,
    meeting_out,
)
from shosai.features.meetings.domain.meetings import TitleRuleError


def build_meetings_router(
    services: tuple[MeetingLibrary, MeetingDeletion], ports: PortDirectory
) -> APIRouter:
    """The library, a meeting's page, its change and its deletion."""
    library, deletion = services
    router = APIRouter(prefix="/v1/meetings", tags=["meetings"])
    signed_in = bearer_principal(ports)

    @router.get("")
    async def list_meetings(
        principal: Annotated[Principal, Depends(signed_in)],
        page: PageParameters,
        folder: Annotated[
            UUID | Literal["none"] | None,
            Query(description="One of your folders by id, or `none` for your meetings in none."),
        ] = None,
        workspace_id: Annotated[
            UUID | None, Query(description="Only the meetings readable in this workspace.")
        ] = None,
    ) -> Page[MeetingCardOut]:
        """The meetings you may read, newest first."""
        narrowing = LibraryFilter(folder=folder, workspace_id=workspace_id)
        cards = await library.page(principal, page, narrowing)
        return Page(
            items=[MeetingCardOut(**card_out(c)) for c in cards.items],
            next_cursor=cards.next_cursor,
        )

    @router.get("/{meeting_id}")
    async def get_meeting(
        principal: Annotated[Principal, Depends(signed_in)], meeting_id: UUID
    ) -> MeetingOut:
        """A meeting you may read."""
        return meeting_out(await library.view(principal, meeting_id))

    @router.patch("/{meeting_id}")
    async def change_meeting(
        principal: Annotated[Principal, Depends(signed_in)],
        meeting_id: UUID,
        body: MeetingChangeIn,
    ) -> MeetingOut:
        """Rename the meeting, or move it into one of your folders or out of it."""
        given = body.model_fields_set
        change = MeetingChange(
            title=body.title,
            folder_id=body.folder_id,
            folder_given="folder_id" in given,
            template_id=body.template_id,
            template_given="template_id" in given,
        )
        try:
            view = await library.change(principal, meeting_id, change)
        except TitleRuleError as error:
            raise AppError(error.code, HTTPStatus.UNPROCESSABLE_ENTITY) from error
        return meeting_out(view)

    @router.delete("/{meeting_id}", status_code=HTTPStatus.NO_CONTENT)
    async def delete_meeting(
        principal: Annotated[Principal, Depends(signed_in)], meeting_id: UUID
    ) -> Response:
        """Delete your meeting: hidden from everyone at once, gone for good after 7 days."""
        await deletion.delete(principal, meeting_id)
        return Response(status_code=HTTPStatus.NO_CONTENT)

    return router
