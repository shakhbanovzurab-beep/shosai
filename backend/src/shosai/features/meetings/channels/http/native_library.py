"""The native library and notes: `/v1/me/sessions`, `…/{id}/full`, `…/{id}/note`, `…/note/draft`.

The shipped clients read a bare array of the person's newest meetings (`status`, `q`,
`limit` from 1 to 200, `offset`), a meeting with its transcript and map, and their own
notes on it beside Leo's write-up; they write their notes with `{markdown, client}`, the
last write winning (MT-D12). The draft's shapes are kept exactly (`native_shapes.py`).
Errors keep the draft's `detail`: 404 `meeting_not_found`, 409 `private_meeting` for a
meeting not kept, 422 `notes_too_long`, `note_client_unknown`.
"""

from http import HTTPStatus
from typing import Annotated, Final
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from shosai.core.kernel.errors import AppError
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import Principal, bearer_principal
from shosai.features.meetings.application.my_notes import MyNotes
from shosai.features.meetings.application.native_library import NEWEST, NativeLibrary
from shosai.features.meetings.channels.http.native_shapes import (
    NoteOut,
    SessionFull,
    SessionRow,
    note_out,
    session_full,
    session_row,
)
from shosai.features.meetings.channels.http.native_words import NativeWords
from shosai.features.meetings.domain.library import NoteClient

DEFAULT_LIMIT: Final = 50


class NoteDraftUpdate(BaseModel):
    """The person's notes as a client sends them; unknown fields are accepted."""

    markdown: str
    client: str = NoteClient.WEB.value


def note_client(raw: str) -> NoteClient:
    """The writing client; `note_client_unknown` for one the platform has not shipped."""
    try:
        return NoteClient(raw)
    except ValueError:
        raise AppError("note_client_unknown", HTTPStatus.UNPROCESSABLE_ENTITY) from None


def build_native_library_router(
    services: tuple[NativeLibrary, MyNotes, NativeWords], ports: PortDirectory
) -> APIRouter:
    """The native library and the person's notes."""
    library, notes, words = services
    router = APIRouter(prefix="/v1/me/sessions", tags=["native"])
    signed_in = bearer_principal(ports)

    @router.get("")
    async def list_my_sessions(
        principal: Annotated[Principal, Depends(signed_in)],
        status: str | None = None,
        q: str | None = None,
        limit: Annotated[int, Query(ge=1, le=NEWEST)] = DEFAULT_LIMIT,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> list[SessionRow]:
        """Your newest meetings, at most the 200 newest that match."""
        rows = await library.rows(principal, (status, q), (limit, offset))
        return [session_row(row) for row in rows]

    @router.get("/{session_id}/full")
    async def get_my_session_full(
        principal: Annotated[Principal, Depends(signed_in)], session_id: UUID
    ) -> SessionFull:
        """The meeting with its transcript and map."""
        return session_full(await library.full(principal, session_id), words)

    @router.get("/{session_id}/note")
    async def get_my_note(
        principal: Annotated[Principal, Depends(signed_in)], session_id: UUID
    ) -> NoteOut:
        """Your notes on the meeting, beside Leo's write-up."""
        return note_out(await library.note(principal, session_id), words)

    @router.put("/{session_id}/note/draft")
    async def update_my_note_draft(
        principal: Annotated[Principal, Depends(signed_in)],
        session_id: UUID,
        body: NoteDraftUpdate,
    ) -> NoteOut:
        """Replace your notes on the meeting; the last write wins."""
        await notes.write(principal, session_id, body.markdown, (note_client(body.client), True))
        return note_out(await library.note(principal, session_id), words)

    return router
