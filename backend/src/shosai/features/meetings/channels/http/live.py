"""A broadcast by its link: `/v1/meetings/live/{token}` (MR-D7, meetings A12b).

`join` answers whoever opens the link and `knock` whoever waits in the waiting room, signed
in or as a guest; the rest take the room pass the ticket gave, of this link's room. Errors:
`not_found` (404), `removed` (403), `room_pass_invalid` (401), `room_finished` (410),
`not_allowed` (403), `on_stage`, `not_invited`, `stage_full`, `chat_closed` and
`broadcast_not_live` (409), `hand_not_found`, `knock_not_found` and `member_not_found` (404),
`rate_limited` (429 with its wait), `video_unavailable` (503).
"""

from datetime import timedelta
from http import HTTPStatus
from typing import Annotated, Final

from fastapi import APIRouter, Depends, Query

from shosai.core.idempotency.http import IdempotencyKeyHeader
from shosai.core.kv.rate_limits import RateLimit, RateLimiter
from shosai.core.ports.directory import PortDirectory
from shosai.core.web.rate_limit import rate_limited
from shosai.features.identity.contracts import Principal as Person
from shosai.features.meetings.application.broadcast_chat import BroadcastChat
from shosai.features.meetings.application.broadcast_entry import BroadcastDoor
from shosai.features.meetings.application.broadcast_stage import BroadcastStage, SeatChange
from shosai.features.meetings.application.joining import JoinDesk
from shosai.features.meetings.application.passes import PassCheck
from shosai.features.meetings.channels.http import broadcast_models as models
from shosai.features.meetings.channels.http.joining import JOINS, RoomPassHeader, optional_person
from shosai.features.meetings.contracts import RoomNotFoundError
from shosai.features.meetings.domain.broadcasts import StageRole
from shosai.features.meetings.infrastructure.room_passes import PassHolder

# Зритель в зале ожидания спрашивает о впуске раз в 3 с: до 20 раз в минуту, с запасом.
KNOCKS: Final = RateLimit(
    "meetings_broadcast_knock", rate=30, period=timedelta(minutes=1), burst=10
)
LiveServices = tuple[BroadcastDoor, BroadcastStage, BroadcastChat]


def build_live_router(
    services: LiveServices,
    desk: JoinDesk,
    check: PassCheck,
    gates: tuple[PortDirectory, RateLimiter],
) -> APIRouter:
    """The broadcast's link and its routes for the stage and the audience."""
    door, stage, chat = services
    ports, limiter = gates
    router = APIRouter(prefix="/v1/meetings/live/{token}", tags=["meetings"])
    signed_in_or_guest = Annotated[Person | None, Depends(optional_person(ports))]

    async def holder_of(token: str, room_pass: str | None) -> PassHolder:
        holder = await check.holder(room_pass)
        if (await desk.find(token)).room_id != holder.room_id:
            raise RoomNotFoundError
        return holder

    @router.post("/join", dependencies=[Depends(rate_limited(limiter, JOINS))])
    async def join_meeting_broadcast(
        token: str, person: signed_in_or_guest, body: models.LiveJoinIn
    ) -> models.LiveTicketOut:
        """Open a broadcast by its link: the stage, the audience, the waiting room or why not."""
        return models.ticket_out(await door.join(token, person, body.name))

    @router.post("/knock", dependencies=[Depends(rate_limited(limiter, KNOCKS))])
    async def knock_meeting_broadcast(token: str, body: models.LiveKnockIn) -> models.LiveTicketOut:
        """Ask whether the waiting room let you in."""
        return models.ticket_out(await door.knock(token, body.knock))

    @router.get("/state")
    async def get_meeting_broadcast_state(
        token: str, room_pass: RoomPassHeader = None
    ) -> models.LiveStateOut:
        """The broadcast's state: the stage, the viewers and, for the host, the queues."""
        return models.state_out(await stage.state(await holder_of(token, room_pass)))

    @router.post("/chat", status_code=HTTPStatus.CREATED)
    async def send_meeting_broadcast_message(
        token: str,
        body: models.LiveChatIn,
        key: IdempotencyKeyHeader,
        room_pass: RoomPassHeader = None,
    ) -> models.LiveChatMessageOut:
        """Send a message to the broadcast's chat."""
        holder = await holder_of(token, room_pass)
        return models.message_out(await chat.send(holder, body.text, key), holder.principal)

    @router.get("/chat")
    async def list_meeting_broadcast_messages(
        token: str,
        after: Annotated[int, Query(ge=0, description="The last `seq` you hold; 0 for all.")] = 0,
        limit: Annotated[int, Query(ge=1, le=models.PAGE_MAX)] = models.PAGE_MAX,
        room_pass: RoomPassHeader = None,
    ) -> models.LiveChatPageOut:
        """The broadcast's messages after a number, oldest first."""
        holder = await holder_of(token, room_pass)
        items, following = await chat.history(holder, after, limit)
        return models.LiveChatPageOut(
            items=[models.message_out(item, holder.principal) for item in items],
            next_cursor=None if following is None else str(following),
        )

    return router


def build_live_stage_router(
    services: tuple[BroadcastDoor, BroadcastStage], desk: JoinDesk, check: PassCheck
) -> APIRouter:
    """The broadcast's hands, waiting room and stage, with the room pass."""
    door, stage = services
    router = APIRouter(prefix="/v1/meetings/live/{token}", tags=["meetings"])

    async def holder_of(token: str, room_pass: str | None) -> PassHolder:
        holder = await check.holder(room_pass)
        if (await desk.find(token)).room_id != holder.room_id:
            raise RoomNotFoundError
        return holder

    @router.put("/hand", status_code=HTTPStatus.NO_CONTENT)
    async def put_meeting_broadcast_hand(
        token: str, body: models.LiveHandIn, room_pass: RoomPassHeader = None
    ) -> None:
        """Raise or lower your hand to ask to speak."""
        await stage.raise_hand(await holder_of(token, room_pass), raised=body.raised)

    @router.post("/hands/{principal}", status_code=HTTPStatus.NO_CONTENT)
    async def answer_meeting_broadcast_hand(
        token: str, principal: str, body: models.LiveInviteIn, room_pass: RoomPassHeader = None
    ) -> None:
        """Invite the hand's viewer to the stage, or decline the hand."""
        await stage.answer_hand(await holder_of(token, room_pass), principal, invite=body.invite)

    @router.post("/admissions/{knock_id}", status_code=HTTPStatus.NO_CONTENT)
    async def answer_meeting_broadcast_knock(
        token: str, knock_id: str, body: models.LiveAdmitIn, room_pass: RoomPassHeader = None
    ) -> None:
        """Let a knock in, or turn it away."""
        await stage.admit(await holder_of(token, room_pass), knock_id, admitted=body.admitted)

    @router.patch("/members/{principal}", status_code=HTTPStatus.NO_CONTENT)
    async def patch_meeting_broadcast_member(
        token: str, principal: str, body: models.LiveSeatIn, room_pass: RoomPassHeader = None
    ) -> None:
        """Take a speaker off air or back, or name or unname a co-host."""
        role = None if body.role is None else StageRole(body.role)
        change = SeatChange(on_air=body.on_air, role=role)
        await stage.change_seat(await holder_of(token, room_pass), principal, change)

    @router.delete("/members/{principal}", status_code=HTTPStatus.NO_CONTENT)
    async def delete_meeting_broadcast_member(
        token: str, principal: str, room_pass: RoomPassHeader = None
    ) -> None:
        """Take someone off the stage; they keep watching."""
        await stage.remove_seat(await holder_of(token, room_pass), principal)

    @router.post("/stage", status_code=HTTPStatus.NO_CONTENT)
    async def step_on_meeting_broadcast_stage(token: str, room_pass: RoomPassHeader = None) -> None:
        """Take the place on the stage the host invited you to."""
        await door.step_on_stage(await holder_of(token, room_pass))

    return router
