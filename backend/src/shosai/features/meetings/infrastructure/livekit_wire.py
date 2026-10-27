"""LiveKit's messages as meetings' values: rooms, participants and webhooks.

LiveKit gives times in seconds or milliseconds since the epoch; the values here are aware
UTC times, the millisecond field preferred when it is set. A webhook's body is protobuf's
JSON — camelCase names, 64-bit integers as strings — read by a typed model of the fields
meetings uses; anything else in it is ignored. A webhook of a kind meetings does not handle
is kept as `other`, so a newer server never breaks the route.
"""

from datetime import UTC, datetime
from typing import Final

from livekit.protocol.models import ParticipantInfo, Room
from pydantic import BaseModel, ConfigDict, Field

from shosai.features.meetings.application.video_server import (
    EgressReport,
    SfuParticipant,
    SfuRoom,
    SfuWebhook,
    WebhookKind,
)

MILLISECONDS: Final = 1_000
NANOSECONDS: Final = 1_000_000_000
KNOWN_KINDS: Final = frozenset(kind.value for kind in WebhookKind)


def utc_time(seconds: int, milliseconds: int = 0) -> datetime:
    """A LiveKit time as an aware UTC time; milliseconds win when given."""
    if milliseconds:
        return datetime.fromtimestamp(milliseconds / MILLISECONDS, UTC)
    return datetime.fromtimestamp(seconds, UTC)


def room_of(room: Room) -> SfuRoom:
    """An SFU room from LiveKit's `Room`."""
    return SfuRoom(
        name=room.name,
        sid=room.sid,
        participants=room.num_participants,
        metadata=room.metadata,
        created_at=utc_time(room.creation_time, room.creation_time_ms),
        max_participants=room.max_participants,
    )


def participant_of(participant: ParticipantInfo) -> SfuParticipant:
    """A session from LiveKit's `ParticipantInfo`."""
    return SfuParticipant(
        identity=participant.identity,
        name=participant.name,
        joined_at=utc_time(participant.joined_at, participant.joined_at_ms),
        attributes=dict(participant.attributes),
    )


class WireRoom(BaseModel):
    """The room of a webhook."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    name: str = ""
    sid: str = ""
    participants: int = Field(default=0, alias="numParticipants")
    ceiling: int = Field(default=0, alias="maxParticipants")


class WireParticipant(BaseModel):
    """The participant of a webhook."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    identity: str = ""


class WireFile(BaseModel):
    """A file an egress wrote."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    size: int = 0
    duration: int = 0


class WireEgress(BaseModel):
    """The egress of a webhook."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    egress_id: str = Field(default="", alias="egressId")
    room_name: str = Field(default="", alias="roomName")
    status: str = "EGRESS_STARTING"
    file_results: list[WireFile] = Field(default_factory=list, alias="fileResults")
    error: str = ""

    def report(self) -> EgressReport:
        """The egress as meetings reads it."""
        return EgressReport(
            egress_id=self.egress_id,
            room_name=self.room_name,
            status=self.status,
            size_bytes=max((item.size for item in self.file_results), default=0),
            duration_seconds=max((item.duration for item in self.file_results), default=0)
            // NANOSECONDS,
            error=self.error,
        )


class WireWebhook(BaseModel):
    """A webhook's body as LiveKit sends it."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    event: str
    id: str = ""
    created_at: int = Field(default=0, alias="createdAt")
    room: WireRoom | None = None
    participant: WireParticipant | None = None
    egress: WireEgress | None = Field(default=None, alias="egressInfo")


def webhook_of(body: bytes) -> SfuWebhook:
    """A verified webhook's body as meetings' value; `ValidationError` on a body that is not one."""
    wire = WireWebhook.model_validate_json(body)
    room = wire.room or WireRoom()
    return SfuWebhook(
        id=wire.id,
        kind=WebhookKind(wire.event) if wire.event in KNOWN_KINDS else WebhookKind.OTHER,
        created_at=utc_time(wire.created_at),
        room_name=room.name,
        room_sid=room.sid,
        participants=None if wire.room is None else room.participants,
        identity=None if wire.participant is None else wire.participant.identity,
        ceiling=None if wire.room is None or not room.ceiling else room.ceiling,
        egress=None if wire.egress is None else wire.egress.report(),
    )
