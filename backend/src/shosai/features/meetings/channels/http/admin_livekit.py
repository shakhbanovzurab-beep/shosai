"""The admin's LiveKit screen: `/v1/admin/livekit/*` (meetings plan §3.3, MR-D10).

The admin session gates every route. The overview answers even when LiveKit or Prometheus
does not: the server's health says so and the numbers Prometheus gives are null. A room is
named by its LiveKit name; reading it, ending it and removing a session answer
`room_not_found` for a room the SFU or meetings does not hold. Errors: `room_not_found`,
`participant_not_found`, `cannot_remove_owner`, `video_unavailable`, `admin_sign_in_required`.
"""

from collections.abc import Sequence
from datetime import datetime
from http import HTTPStatus
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Path, Response
from pydantic import BaseModel, ConfigDict, Field

from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import require_admin
from shosai.features.meetings.application.admin_actions import AdminRoomActions
from shosai.features.meetings.application.admin_views import (
    EgressLine,
    LiveKitHealth,
    NodeView,
    RoomLine,
    SessionView,
)
from shosai.features.meetings.application.admin_watch import LiveKitWatch
from shosai.features.meetings.application.video_server import TrackKind

# Имя комнаты и identity LiveKit: без слэшей и управляющих символов.
SEGMENT = r"^[^/\x00-\x1f\x7f]+$"
SEGMENT_MAX = 256
RoomName = Annotated[str, Path(max_length=SEGMENT_MAX, pattern=SEGMENT)]
Identity = Annotated[str, Path(max_length=SEGMENT_MAX, pattern=SEGMENT)]


class Out(BaseModel):
    """A response shape: every field is always sent."""

    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


class LiveKitServerOut(Out):
    """The server's card."""

    url: str | None = Field(description="The signalling address clients use; null when not set.")
    started_at: datetime | None = Field(description="When the longest-running node started.")
    health: LiveKitHealth
    api_key_configured: bool


class LiveKitStatsOut(Out):
    """The numbers across the server; null where Prometheus gave no data."""

    active_rooms: int
    participants: int
    published_tracks: int | None
    bandwidth_in_mbps: float | None
    bandwidth_out_mbps: float | None
    active_egress: int = Field(description="Egress jobs starting, running or ending.")


class LiveKitHistoryPointOut(Out):
    """One sample of the last 24 hours."""

    at: datetime
    participants: int
    bandwidth_in_mbps: float
    bandwidth_out_mbps: float


class LiveKitNodeOut(Out):
    """One node; its load is null when unknown."""

    id: str
    cpu_percent: float | None = Field(description="Of the CPUs the node may use.")
    memory_percent: float | None = Field(description="Of the node's memory limit.")
    rooms: int
    participants: int
    state: Literal["serving", "down"]


class LiveKitRoomOut(Out):
    """A room the SFU holds."""

    name: str = Field(description="The LiveKit room name; used in the room's URLs.")
    started_at: datetime
    num_participants: int
    recording: bool
    video_codec: str | None
    audio_codec: str | None


class LiveKitEgressOut(Out):
    """An egress job the SFU runs or still remembers."""

    id: str
    room_name: str
    status: Literal["starting", "active", "ending", "complete", "failed"]
    started_at: datetime | None
    ended_at: datetime | None
    file_size_bytes: int | None = Field(description="Null until the file is written.")


class LiveKitOverviewOut(Out):
    """The admin's LiveKit screen at one moment."""

    server: LiveKitServerOut
    stats: LiveKitStatsOut
    history: list[LiveKitHistoryPointOut] = Field(description="Oldest first; empty: no data.")
    nodes: list[LiveKitNodeOut]
    rooms: list[LiveKitRoomOut]
    egress: list[LiveKitEgressOut] = Field(description="The latest first.")
    updated_at: datetime


class LiveKitTrackOut(Out):
    """A track a session publishes."""

    sid: str
    kind: TrackKind
    muted: bool


class LiveKitDeviceOut(Out):
    """The device a session joined from, as its client declared it; null when not declared."""

    os: str | None
    os_version: str | None
    client: str | None
    client_version: str | None
    browser: str | None


class LiveKitParticipantOut(Out):
    """A session in the room."""

    identity: str
    name: str
    joined_at: datetime
    device: LiveKitDeviceOut
    tracks: list[LiveKitTrackOut]


class LiveKitRoomDetailOut(LiveKitRoomOut):
    """A room with the sessions in it."""

    participants: list[LiveKitParticipantOut]


def room_out(line: RoomLine) -> LiveKitRoomOut:
    """A room's line."""
    return LiveKitRoomOut(
        name=line.name, started_at=line.started_at, num_participants=line.participants,
        recording=line.recording, video_codec=line.video_codec, audio_codec=line.audio_codec,
    )  # fmt: skip


def node_out(node: NodeView) -> LiveKitNodeOut:
    """A node's row."""
    return LiveKitNodeOut(
        id=node.id, cpu_percent=node.cpu_percent, memory_percent=node.memory_percent,
        rooms=node.rooms, participants=node.participants,
        state="serving" if node.serving else "down",
    )  # fmt: skip


def egress_out(line: EgressLine) -> LiveKitEgressOut:
    """An egress row."""
    return LiveKitEgressOut.model_validate(line, from_attributes=True)


def participants_out(sessions: Sequence[SessionView]) -> list[LiveKitParticipantOut]:
    """The room's sessions."""
    return [
        LiveKitParticipantOut(
            identity=item.identity,
            name=item.name,
            joined_at=item.joined_at,
            device=LiveKitDeviceOut.model_validate(item.device, from_attributes=True),
            tracks=[
                LiveKitTrackOut(sid=track.sid, kind=track.kind, muted=track.muted)
                for track in item.tracks
            ],
        )
        for item in sessions
    ]


def build_admin_livekit_router(
    watch: LiveKitWatch, actions: AdminRoomActions, ports: PortDirectory
) -> APIRouter:
    """The admin's routes over LiveKit."""
    router = APIRouter(
        prefix="/v1/admin/livekit", tags=["admin"], dependencies=[Depends(require_admin(ports))]
    )

    @router.get("/overview")
    async def livekit_overview() -> LiveKitOverviewOut:
        """The server, its load and day, its nodes, rooms and egress jobs."""
        seen = await watch.overview()
        return LiveKitOverviewOut(
            server=LiveKitServerOut.model_validate(seen.server, from_attributes=True),
            stats=LiveKitStatsOut.model_validate(seen.load, from_attributes=True),
            history=[
                LiveKitHistoryPointOut.model_validate(point, from_attributes=True)
                for point in seen.history
            ],
            nodes=[node_out(node) for node in seen.nodes],
            rooms=[room_out(line) for line in seen.rooms],
            egress=[egress_out(line) for line in seen.egress],
            updated_at=seen.updated_at,
        )

    @router.get("/rooms/{name}")
    async def livekit_room(name: RoomName) -> LiveKitRoomDetailOut:
        """A room the SFU holds, with the sessions in it."""
        detail = await watch.room(name)
        line = room_out(detail.room)
        return LiveKitRoomDetailOut(
            **line.model_dump(), participants=participants_out(detail.sessions)
        )

    @router.delete("/rooms/{name}", status_code=HTTPStatus.NO_CONTENT)
    async def end_livekit_room(name: RoomName) -> Response:
        """End the room for everyone and close it for good; audited."""
        await actions.end(name)
        return Response(status_code=HTTPStatus.NO_CONTENT)

    @router.delete("/rooms/{name}/participants/{identity}", status_code=HTTPStatus.NO_CONTENT)
    async def remove_livekit_participant(name: RoomName, identity: Identity) -> Response:
        """Ban the session's person or guest from the room and disconnect them; audited."""
        await actions.remove(name, identity)
        return Response(status_code=HTTPStatus.NO_CONTENT)

    return router
