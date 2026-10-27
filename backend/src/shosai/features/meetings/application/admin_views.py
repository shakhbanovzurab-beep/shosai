"""What the admin's LiveKit screen shows: the server, its load, nodes, rooms, egress and sessions.

Values of `LiveKitWatch` (`admin_watch.py`) for the routes; a None is "no data" — Prometheus gave
none, or a client did not declare it.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from shosai.features.meetings.application.sfu_metrics import LoadSample
from shosai.features.meetings.application.video_server import SfuTrack


class LiveKitHealth(StrEnum):
    """How the server stands as the screen sums it up."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"


@dataclass(frozen=True, slots=True)
class ServerFacts:
    """What the deploy tells about LiveKit: its public address and its memory limit."""

    url: str | None
    configured: bool
    memory_limit_mb: int | None


@dataclass(frozen=True, slots=True)
class ServerView:
    """The server's card."""

    url: str | None
    started_at: datetime | None
    health: LiveKitHealth
    api_key_configured: bool


@dataclass(frozen=True, slots=True)
class LoadView:
    """The numbers across the server; None where Prometheus gave no data."""

    active_rooms: int
    participants: int
    published_tracks: int | None
    bandwidth_in_mbps: float | None
    bandwidth_out_mbps: float | None
    active_egress: int


@dataclass(frozen=True, slots=True)
class NodeView:
    """One node: its load, its rooms and whether it serves."""

    id: str
    cpu_percent: float | None
    memory_percent: float | None
    rooms: int
    participants: int
    serving: bool


@dataclass(frozen=True, slots=True)
class RoomLine:
    """A room the SFU holds, by its LiveKit name."""

    name: str
    started_at: datetime
    participants: int
    recording: bool
    video_codec: str | None = None
    audio_codec: str | None = None


@dataclass(frozen=True, slots=True)
class EgressLine:
    """An egress the SFU runs or still remembers."""

    id: str
    room_name: str
    status: str
    started_at: datetime | None
    ended_at: datetime | None
    file_size_bytes: int | None


@dataclass(frozen=True, slots=True)
class Overview:
    """The whole screen at one moment."""

    server: ServerView
    load: LoadView
    history: Sequence[LoadSample]
    nodes: Sequence[NodeView]
    rooms: Sequence[RoomLine]
    egress: Sequence[EgressLine]
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class DeviceView:
    """The device a session joined from, as its client declared it at the join."""

    os: str | None
    os_version: str | None
    client: str | None
    client_version: str | None
    browser: str | None


@dataclass(frozen=True, slots=True)
class SessionView:
    """A session in a room: who, since when, from what and what it publishes."""

    identity: str
    name: str
    joined_at: datetime
    device: DeviceView
    tracks: Sequence[SfuTrack]


@dataclass(frozen=True, slots=True)
class RoomDetail:
    """A room with the sessions in it."""

    room: RoomLine
    sessions: Sequence[SessionView]
