"""The owner's rooms: `/v1/meetings/rooms` (meetings plan §3.3, frontend/docs/meetings-api.md).

"New meeting" opens a room once per `Idempotency-Key` and answers its link; the section's
Live lists the person's rooms with a call going on, by cursor; the owner reads, renames,
switches notes for and ends a room. Another person's room, or one in a space the person is
not in, is `room_not_found`. Errors use the platform's envelope: `room_not_found`,
`workspace_not_found`, `room_closed`, `title_too_long`, `video_unavailable`, `invalid_cursor`,
`validation_error`, `idempotency_key_reused`.
"""

from datetime import datetime
from http import HTTPStatus
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, ConfigDict, Field

from shosai.core.idempotency.http import IdempotencyKeyHeader
from shosai.core.pagination.page import PageParameters
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import Principal, bearer_principal
from shosai.features.meetings.application.removals import Removals
from shosai.features.meetings.application.room_reads import RoomView
from shosai.features.meetings.application.rooms import RoomBook, RoomChange
from shosai.features.meetings.domain.invites import room_link
from shosai.features.meetings.domain.rooms import TITLE_MAX, RoomState


class Strict(BaseModel):
    """A request body: a field the contract does not know is refused."""

    model_config = ConfigDict(extra="forbid")


class Out(BaseModel):
    """A response shape: every field is always sent."""

    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


class CallOut(Out):
    """The call going on in a room."""

    started_at: datetime
    participants: int | None = Field(description="How many are in the call; null when unknown.")


class RoomOut(Out):
    """A room as its owner sees it."""

    id: UUID
    title: str | None = Field(description="Null for an untitled room; the cabinet names it.")
    state: RoomState
    notes_on: bool = Field(description="Leo takes notes of the room's calls.")
    workspace_id: UUID | None
    link: str = Field(description="The invitation: `https://…/meet/{token}`.")
    created_at: datetime
    closed_at: datetime | None
    call: CallOut | None


class RoomsPageOut(Out):
    """A page of rooms and the next page's cursor."""

    items: list[RoomOut]
    next_cursor: str | None


class NewRoom(Strict):
    """A room in Personal, or in a workspace the person belongs to."""

    title: str | None = Field(default=None, max_length=TITLE_MAX * 2)
    workspace_id: UUID | None = None


class HandPatch(Strict):
    """Lower a hand; only lowering is the owner's."""

    raised: Literal[False]


class RoomPatch(Strict):
    """A new title (empty clears it), the notes switch, or both."""

    title: str | None = Field(default=None, max_length=TITLE_MAX * 2)
    notes_on: bool | None = None


def room_out(view: RoomView, origin: str) -> RoomOut:
    """The contract's shape of a room."""
    room, call = view.room, view.call
    return RoomOut(
        id=room.id,
        title=room.title,
        state=room.state,
        notes_on=room.notes_on,
        workspace_id=room.org_id,
        link=room_link(origin, view.invite_token),
        created_at=view.created_at,
        closed_at=room.closed_at,
        call=None
        if call is None
        else CallOut(started_at=call.started_at, participants=call.participants),
    )


def build_rooms_router(
    services: tuple[RoomBook, Removals], ports: PortDirectory, origin: str
) -> APIRouter:
    """The owner's rooms, their participants and hands."""
    book, removals = services
    router = APIRouter(prefix="/v1/meetings/rooms", tags=["meetings"])
    signed_in = Annotated[Principal, Depends(bearer_principal(ports))]

    @router.post("", status_code=HTTPStatus.CREATED)
    async def create_meeting_room(
        principal: signed_in, body: NewRoom, key: IdempotencyKeyHeader
    ) -> RoomOut:
        """Open a room; its link is the invitation."""
        view = await book.create(principal, body.title, body.workspace_id, key)
        return room_out(view, origin)

    @router.get("")
    async def list_meeting_rooms(
        principal: signed_in,
        page: PageParameters,
        state: Annotated[
            Literal["live"], Query(description="`live`: rooms with a call going on.")
        ] = "live",
        workspace_id: Annotated[
            UUID | None, Query(description="A workspace; Personal if absent.")
        ] = None,
    ) -> RoomsPageOut:
        """Your rooms with a call going on, latest call first."""
        del state
        views, cursor = await book.live(principal, workspace_id, page)
        return RoomsPageOut(items=[room_out(view, origin) for view in views], next_cursor=cursor)

    @router.get("/{room_id}")
    async def get_meeting_room(principal: signed_in, room_id: UUID) -> RoomOut:
        """Your room, with its call if one goes on."""
        return room_out(await book.read(principal, room_id), origin)

    @router.patch("/{room_id}")
    async def patch_meeting_room(principal: signed_in, room_id: UUID, body: RoomPatch) -> RoomOut:
        """Rename your room or switch Leo's notes; everyone in the call sees the mark."""
        change = RoomChange(title=body.title, notes_on=body.notes_on)
        return room_out(await book.change(principal, room_id, change), origin)

    @router.post("/{room_id}/end")
    async def end_meeting_room(principal: signed_in, room_id: UUID) -> RoomOut:
        """End the call for everyone and close the room for good."""
        return room_out(await book.end(principal, room_id), origin)

    @router.delete(
        "/{room_id}/participants/{identity}",
        status_code=HTTPStatus.NO_CONTENT,
        response_class=Response,
    )
    async def remove_meeting_participant(
        principal: signed_in, room_id: UUID, identity: str
    ) -> None:
        """Remove someone from the call; they cannot come back to this room."""
        await removals.remove(principal, room_id, identity)

    @router.patch(
        "/{room_id}/participants/{identity}/hand",
        status_code=HTTPStatus.NO_CONTENT,
        response_class=Response,
    )
    async def lower_meeting_hand(
        principal: signed_in, room_id: UUID, identity: str, body: HandPatch
    ) -> None:
        """Lower someone's raised hand."""
        del body
        await removals.lower_hand(principal, room_id, identity)

    return router
