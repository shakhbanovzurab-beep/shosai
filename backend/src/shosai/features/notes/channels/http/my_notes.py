"""A person's own notes on a meeting and its participants (plan step 7b).

`GET` and `PUT /v1/notes/{id}/my-notes` read and replace what the person typed on a
meeting they may read — their own, empty before they write any, never anyone else's: last
write wins, the version grows by one. `POST …/participants` adds a participant by address —
201 when added, 200 with the one already there — and `DELETE …/participants/{id}` removes
one a person added. Errors: `meeting_not_found`, `notes_too_long`,
`meeting_read_only`, `participant_email_invalid`, `participants_limit_reached`,
`participant_not_found`, `participant_not_removable`.
"""

from http import HTTPStatus
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response

from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import Principal, bearer_principal
from shosai.features.notes.application.my_notes import MyNotes
from shosai.features.notes.application.participants import Participants
from shosai.features.notes.channels.http.library_models import (
    MyNotesIn,
    MyNotesOut,
    ParticipantIn,
    notes_out,
)
from shosai.features.notes.channels.http.meeting_models import ParticipantOut


def build_my_notes_router(
    services: tuple[MyNotes, Participants], ports: PortDirectory
) -> APIRouter:
    """A person's own notes and the participants of a meeting."""
    notes, participants = services
    router = APIRouter(prefix="/v1/notes", tags=["notes"])
    signed_in = bearer_principal(ports)

    @router.get("/{meeting_id}/my-notes")
    async def get_my_notes(
        principal: Annotated[Principal, Depends(signed_in)], meeting_id: UUID
    ) -> MyNotesOut:
        """Your own notes on the meeting; nobody else's."""
        return notes_out(await notes.read(principal, meeting_id))

    @router.put("/{meeting_id}/my-notes")
    async def put_my_notes(
        principal: Annotated[Principal, Depends(signed_in)], meeting_id: UUID, body: MyNotesIn
    ) -> MyNotesOut:
        """Replace your own notes on the meeting."""
        return notes_out(await notes.write(principal, meeting_id, body.text))

    @router.post("/{meeting_id}/participants", status_code=HTTPStatus.CREATED)
    async def add_participant(
        principal: Annotated[Principal, Depends(signed_in)],
        meeting_id: UUID,
        body: ParticipantIn,
        response: Response,
    ) -> ParticipantOut:
        """Add a participant by address; the one already there answers 200."""
        added = await participants.add(principal, meeting_id, (body.email, body.name))
        if not added.created:
            response.status_code = HTTPStatus.OK
        person = added.participant
        return ParticipantOut(
            id=person.id, name=person.name, email=person.email, source=person.source
        )

    @router.delete("/{meeting_id}/participants/{participant_id}", status_code=HTTPStatus.NO_CONTENT)
    async def remove_participant(
        principal: Annotated[Principal, Depends(signed_in)],
        meeting_id: UUID,
        participant_id: UUID,
    ) -> Response:
        """Remove a participant someone added."""
        await participants.remove(principal, meeting_id, participant_id)
        return Response(status_code=HTTPStatus.NO_CONTENT)

    return router
