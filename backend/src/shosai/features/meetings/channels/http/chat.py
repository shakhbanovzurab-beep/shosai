"""The call's chat: `/v1/meetings/rooms/{room_id}/chat` with the room pass (MR-D11).

`POST` keeps a message once per `Idempotency-Key` and publishes it on topic `chat`; `GET` reads
the live call's messages after a sequence the client holds, for a late joiner or a reconnect.
Errors: `room_pass_invalid` (401), `removed` (403), `room_finished` (410), `room_not_found` for a
pass of another room (404), `no_live_call` (409), `text_required` and `text_too_long` (422),
`rate_limited` (429 with its wait), `idempotency_key_reused` (422).
"""

from datetime import datetime
from http import HTTPStatus
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Query
from pydantic import BaseModel, ConfigDict, Field

from shosai.core.idempotency.http import IdempotencyKeyHeader
from shosai.features.meetings.application.chat import Chat
from shosai.features.meetings.application.passes import PassCheck
from shosai.features.meetings.contracts import RoomNotFoundError
from shosai.features.meetings.domain.chat import HISTORY_PAGE_MAX, TEXT_MAX, ChatMessage
from shosai.features.meetings.infrastructure.room_passes import PassHolder

RoomPassHeader = Annotated[
    str | None,
    Header(alias="X-Room-Pass", description="The room pass the join gave this session."),
]


class Strict(BaseModel):
    """A request body: a field the contract does not know is refused."""

    model_config = ConfigDict(extra="forbid")


class Out(BaseModel):
    """A response shape: every field is always sent."""

    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


class MeetingChatMessageIn(Strict):
    """A message's text, 1 to 2 000 characters once trimmed."""

    text: str = Field(max_length=TEXT_MAX * 2)


class MeetingChatMessageOut(Out):
    """A message of the call."""

    id: UUID
    seq: int
    identity: str = Field(description="The sender's session.")
    author: str
    text: str
    sent_at: datetime


class MeetingChatPageOut(Out):
    """Messages after a sequence; a non-null `next_cursor` is the `after` of the next page."""

    items: list[MeetingChatMessageOut]
    next_cursor: str | None


def message_out(message: ChatMessage) -> MeetingChatMessageOut:
    """The contract's shape of a message."""
    return MeetingChatMessageOut(
        id=message.id, seq=message.seq, identity=message.identity, author=message.author,
        text=message.text, sent_at=message.sent_at,
    )  # fmt: skip


def build_chat_router(chat: Chat, check: PassCheck) -> APIRouter:
    """The call's chat, for everyone with a room pass."""
    router = APIRouter(prefix="/v1/meetings/rooms/{room_id}/chat", tags=["meetings"])

    async def holder_of(room_id: UUID, room_pass: str | None) -> PassHolder:
        holder = await check.holder(room_pass)
        if holder.room_id != room_id:
            raise RoomNotFoundError
        return holder

    @router.post("", status_code=HTTPStatus.CREATED)
    async def send_meeting_chat_message(
        room_id: UUID,
        body: MeetingChatMessageIn,
        key: IdempotencyKeyHeader,
        room_pass: RoomPassHeader = None,
    ) -> MeetingChatMessageOut:
        """Send a message to everyone in the call."""
        holder = await holder_of(room_id, room_pass)
        return message_out(await chat.send(holder, body.text, key))

    @router.get("")
    async def list_meeting_chat_messages(
        room_id: UUID,
        after: Annotated[int, Query(ge=0, description="The last `seq` you hold; 0 for all.")] = 0,
        limit: Annotated[int, Query(ge=1, le=HISTORY_PAGE_MAX)] = HISTORY_PAGE_MAX,
        room_pass: RoomPassHeader = None,
    ) -> MeetingChatPageOut:
        """The call's messages after a sequence, oldest first."""
        holder = await holder_of(room_id, room_pass)
        page = await chat.history(holder, after, limit)
        cursor = None if page.next_after is None else str(page.next_after)
        return MeetingChatPageOut(
            items=[message_out(item) for item in page.items], next_cursor=cursor
        )

    return router
