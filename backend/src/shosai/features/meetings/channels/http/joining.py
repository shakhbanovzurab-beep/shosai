"""Joining a room by its link and renewing a room pass (meetings plan §3.3).

`POST /v1/meetings/join/{token}` admits anyone with the link — signed in, or a guest with a
name — ten times a minute per address, and answers the LiveKit pass, the room pass and the
room's marks. Refusals: `not_found` (404, an unknown link and a hidden owner alike),
`room_finished` (410), `removed` (403), `room_full` (409), `name_required` and `name_too_long`
(422), `video_unavailable` (503), `rate_limited` (429). `POST /v1/meetings/passes/refresh`
renews a room pass sent as `X-Room-Pass` while the room is open.
"""

from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from http import HTTPStatus
from typing import Annotated, Final, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, ConfigDict, Field

from shosai.core.kernel.errors import AppError
from shosai.core.kv.rate_limits import RateLimit, RateLimiter
from shosai.core.ports.directory import PortDirectory
from shosai.core.web.rate_limit import rate_limited
from shosai.features.identity.contracts import AUTHENTICATOR
from shosai.features.identity.contracts import Principal as Person
from shosai.features.meetings.application.joining import Admission, JoinDesk
from shosai.features.meetings.application.passes import PassCheck
from shosai.features.meetings.domain.joining import JOINS_PER_MINUTE, CallRole
from shosai.features.meetings.domain.principals import NAME_MAX
from shosai.features.meetings.domain.wire import ATTRIBUTE_MAX

BEARER: Final = "Bearer "
JOINS: Final = RateLimit(
    "meetings_join", rate=JOINS_PER_MINUTE, period=timedelta(minutes=1), burst=JOINS_PER_MINUTE
)
RoomPassHeader = Annotated[
    str | None,
    Header(alias="X-Room-Pass", description="The room pass the join gave this session."),
]
Attribute = Annotated[str | None, Field(default=None, max_length=ATTRIBUTE_MAX)]


class Strict(BaseModel):
    """A request body: a field the contract does not know is refused."""

    model_config = ConfigDict(extra="forbid")


class Out(BaseModel):
    """A response shape: every field is always sent."""

    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


class Device(Strict):
    """The joining device, shown on the admin's screen."""

    os: Attribute = None
    os_version: Attribute = None
    client: Literal["web", "desktop", "mobile"] | None = None
    client_version: Attribute = None
    browser: Attribute = None


class JoinBody(Strict):
    """A guest's name; a signed-in person joins under their profile's name."""

    name: str | None = Field(default=None, max_length=NAME_MAX * 2)
    device: Device | None = None


class JoinRoomOut(Out):
    """The room as the join page and the call show it."""

    title: str | None
    notes_on: bool = Field(description="Leo is taking notes.")
    recording: bool = Field(description="The call is being recorded.")


class JoinOut(Out):
    """What the session connects and acts with."""

    room: JoinRoomOut
    livekit_url: str
    livekit_token: str = Field(description="Valid 10 minutes, enough to connect.")
    room_pass: str = Field(description="Sent as `X-Room-Pass` to the call's routes.")
    pass_expires_at: datetime
    identity: str
    role: CallRole
    ceiling: int
    room_id: UUID | None = Field(description="The room's id, for its owner only.")


class PassOut(Out):
    """A renewed room pass."""

    room_pass: str
    pass_expires_at: datetime


def optional_person(ports: PortDirectory) -> Callable[..., Awaitable[Person | None]]:
    """A route dependency: the signed-in person, or None for a guest without a token."""

    async def person(authorization: Annotated[str | None, Header()] = None) -> Person | None:
        if not authorization:
            return None
        if not authorization.startswith(BEARER):
            raise AppError("unauthorized", HTTPStatus.UNAUTHORIZED, detail="Missing Bearer token")
        return await ports.get(AUTHENTICATOR).principal(authorization.removeprefix(BEARER))

    return person


def join_out(admission: Admission) -> JoinOut:
    """The contract's shape of an admission."""
    room = admission.room
    return JoinOut(
        room=JoinRoomOut(
            title=room.title, notes_on=admission.marks.notes, recording=admission.marks.recording
        ),
        livekit_url=admission.session.url,
        livekit_token=admission.session.token,
        room_pass=admission.room_pass,
        pass_expires_at=admission.pass_expires_at,
        identity=admission.identity,
        role=admission.role,
        ceiling=admission.ceiling,
        room_id=room.id if admission.role is CallRole.OWNER else None,
    )


def build_joining_router(
    desk: JoinDesk, check: PassCheck, ports: PortDirectory, limiter: RateLimiter
) -> APIRouter:
    """The public join and the room pass's renewal."""
    router = APIRouter(prefix="/v1/meetings", tags=["meetings"])
    signed_in_or_guest = Annotated[Person | None, Depends(optional_person(ports))]

    @router.post("/join/{token}", dependencies=[Depends(rate_limited(limiter, JOINS))])
    async def join_meeting(token: str, person: signed_in_or_guest, body: JoinBody) -> JoinOut:
        """Join a call by its link, signed in or as a guest."""
        device = {} if body.device is None else body.device.model_dump()
        entrant = await desk.entrant(person, body.name, device)
        return join_out(await desk.admit(await desk.find(token), entrant))

    @router.post("/passes/refresh")
    async def refresh_room_pass(room_pass: RoomPassHeader = None) -> PassOut:
        """Renew your room pass while the room is open."""
        renewed = await check.renew(room_pass)
        return PassOut(room_pass=renewed.token, pass_expires_at=renewed.expires_at)

    return router
