"""The SFU as meetings' services see it (meetings plan §3.3): rooms, sessions' passes, webhooks.

The port hides LiveKit: the services create and delete the SFU's rooms, read who is in them,
issue a session's pass with its rights and accept the SFU's webhooks only when they are signed
with the API's secret over the body's hash. When LiveKit is not configured or does not answer,
every call raises `VideoUnavailableError`, which the routes answer as 503 `video_unavailable`;
the rest of the app keeps working.
"""

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from http import HTTPStatus
from typing import Final, Protocol

from shosai.core.kernel.errors import AppError
from shosai.features.meetings.domain.joining import Grants

# Через сколько секунд клиенту стоит повторить, когда видеосервер недоступен.
RETRY_AFTER_SECONDS: Final = 30


class VideoUnavailableError(AppError):
    """LiveKit is not configured or did not answer in time (503)."""

    def __init__(self) -> None:
        super().__init__(
            "video_unavailable",
            HTTPStatus.SERVICE_UNAVAILABLE,
            params={"retry_after_seconds": RETRY_AFTER_SECONDS},
        )


class WebhookRejectedError(AppError):
    """A webhook without a valid signature over its body (401)."""

    def __init__(self) -> None:
        super().__init__("webhook_rejected", HTTPStatus.UNAUTHORIZED)


class WebhookKind(StrEnum):
    """What a webhook tells; the value is LiveKit's event name."""

    ROOM_STARTED = "room_started"
    ROOM_FINISHED = "room_finished"
    PARTICIPANT_JOINED = "participant_joined"
    PARTICIPANT_LEFT = "participant_left"
    PARTICIPANT_CONNECTION_ABORTED = "participant_connection_aborted"
    TRACK_PUBLISHED = "track_published"
    TRACK_UNPUBLISHED = "track_unpublished"
    EGRESS_STARTED = "egress_started"
    EGRESS_UPDATED = "egress_updated"
    EGRESS_ENDED = "egress_ended"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class RoomSpec:
    """An SFU room to create: its name, ceiling and metadata."""

    name: str
    max_participants: int
    metadata: str


@dataclass(frozen=True, slots=True)
class SfuRoom:
    """A room the SFU holds now."""

    name: str
    sid: str
    participants: int
    metadata: str
    created_at: datetime
    # Потолок, с которым комната создана; 0 — без потолка.
    max_participants: int = 0
    # Идёт ли запись композита комнаты, как её видит SFU.
    recording: bool = False


class TrackKind(StrEnum):
    """What a published track carries, as the admin's screen shows it."""

    AUDIO = "audio"
    VIDEO = "video"
    SCREEN = "screen"


@dataclass(frozen=True, slots=True)
class SfuTrack:
    """A track a session publishes: its kind, whether it is muted and its codec's MIME type."""

    sid: str
    kind: TrackKind
    muted: bool
    mime_type: str = ""


@dataclass(frozen=True, slots=True)
class SfuParticipant:
    """A session in an SFU room."""

    identity: str
    name: str
    joined_at: datetime
    attributes: Mapping[str, str] = field(default_factory=dict)
    tracks: tuple[SfuTrack, ...] = ()


@dataclass(frozen=True, slots=True)
class PassRequest:
    """What a session's pass carries: the room, the session, its name, rights and attributes."""

    room_name: str
    identity: str
    name: str
    grants: Grants
    attributes: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SessionPass:
    """A signed pass a client connects with, the address it connects to and when it expires."""

    token: str = field(repr=False)
    url: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class BucketTarget:
    """Where an egress writes: the home's bucket as the egress reaches it, and the key."""

    endpoint: str
    region: str
    bucket: str
    access_key: str = field(repr=False)
    secret: str = field(repr=False)
    key: str


@dataclass(frozen=True, slots=True)
class EgressReport:
    """An egress as the SFU reports it: its state, and the file once written."""

    egress_id: str
    room_name: str
    status: str
    size_bytes: int = 0
    duration_seconds: int = 0
    error: str = ""
    started_at: datetime | None = None
    ended_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class SfuWebhook:
    """A verified webhook: its id for deduplication, its kind, time and subject."""

    id: str
    kind: WebhookKind
    created_at: datetime
    room_name: str
    room_sid: str
    participants: int | None = None
    identity: str | None = None
    # Потолок экземпляра комнаты в SFU, с которым его создали.
    ceiling: int | None = None
    egress: EgressReport | None = None


class VideoServer(Protocol):
    """LiveKit's server API and its signatures."""

    async def create_room(self, spec: RoomSpec) -> SfuRoom:
        """Create the room, or answer the one that already has this name."""
        ...

    async def rooms(self, names: Collection[str] = ()) -> Sequence[SfuRoom]:
        """The rooms the SFU holds, only those named when names are given."""
        ...

    async def delete_room(self, name: str) -> None:
        """End the room for everyone; a room the SFU no longer holds is already gone."""
        ...

    async def participants(self, room_name: str) -> Sequence[SfuParticipant]:
        """The sessions in a room; none when the SFU does not hold it."""
        ...

    async def set_metadata(self, room_name: str, metadata: str) -> bool:
        """Replace a room's metadata; False when the SFU no longer holds the room."""
        ...

    async def remove_participant(self, room_name: str, identity: str) -> bool:
        """Disconnect a session; False when it is no longer in the room."""
        ...

    async def publish(self, room_name: str, topic: str, payload: bytes) -> bool:
        """Send a reliable data packet to everyone in the room.

        LiveKit answers a room no node holds as unavailable, so a finished room raises
        `VideoUnavailableError` like an unreachable SFU; the caller treats both the same.
        """
        ...

    async def set_attributes(
        self, room_name: str, identity: str, attributes: Mapping[str, str]
    ) -> bool:
        """Set a session's attributes, an empty value removing one; False when it is gone."""
        ...

    def session_pass(self, request: PassRequest, now: datetime) -> SessionPass:
        """A pass for one session, valid for the join's 10 minutes."""
        ...

    def verify_webhook(self, body: bytes, authorization: str | None) -> SfuWebhook:
        """The webhook if it is signed over this body; `WebhookRejectedError` otherwise."""
        ...

    async def record(self, room_name: str, target: BucketTarget) -> str:
        """Start the room's video recording into the bucket; its egress id."""
        ...

    async def stop_egress(self, egress_id: str) -> None:
        """Stop an egress; one already over is left as it is."""
        ...

    async def egresses(
        self, room_name: str | None = None, *, active: bool = True
    ) -> Sequence[EgressReport]:
        """The egresses the SFU runs, a room's only when named; with `active` off, also the
        ones over that the SFU still remembers."""
        ...

    async def egress(self, egress_id: str) -> EgressReport | None:
        """One egress as the SFU last saw it, running or over; None when it does not know it."""
        ...

    async def ping(self) -> None:
        """Answer when the SFU's API answers; for the readiness probe."""
        ...
