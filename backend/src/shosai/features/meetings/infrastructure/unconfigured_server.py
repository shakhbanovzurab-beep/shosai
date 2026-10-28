"""The SFU when `LIVEKIT_*` is not set: every call is 503, every webhook 401 (meetings A2).

The app starts without LiveKit; only calls are unavailable, and nothing pretends otherwise.
"""

from collections.abc import Collection, Mapping, Sequence
from datetime import datetime

from shosai.features.meetings.application.video_server import (
    BucketTarget,
    EgressReport,
    PassRequest,
    RoomSpec,
    SessionPass,
    SfuParticipant,
    SfuRoom,
    SfuWebhook,
    VideoUnavailableError,
    WebhookRejectedError,
)
from shosai.features.meetings.domain.joining import Grants


class UnconfiguredVideoServer:
    """The SFU when `LIVEKIT_*` is not set: every call is 503, every webhook 401."""

    async def create_room(self, spec: RoomSpec) -> SfuRoom:
        """Calls are unavailable."""
        raise VideoUnavailableError

    async def rooms(self, names: Collection[str] = ()) -> Sequence[SfuRoom]:
        """Calls are unavailable."""
        raise VideoUnavailableError

    async def delete_room(self, name: str) -> None:
        """Calls are unavailable."""
        raise VideoUnavailableError

    async def participants(self, room_name: str) -> Sequence[SfuParticipant]:
        """Calls are unavailable."""
        raise VideoUnavailableError

    async def set_metadata(self, room_name: str, metadata: str) -> bool:
        """Calls are unavailable."""
        raise VideoUnavailableError

    async def remove_participant(self, room_name: str, identity: str) -> bool:
        """Calls are unavailable."""
        raise VideoUnavailableError

    async def publish(self, room_name: str, topic: str, payload: bytes) -> bool:
        """Calls are unavailable."""
        raise VideoUnavailableError

    async def set_attributes(
        self, room_name: str, identity: str, attributes: Mapping[str, str]
    ) -> bool:
        """Calls are unavailable."""
        raise VideoUnavailableError

    async def set_grants(self, room_name: str, identity: str, grants: Grants) -> bool:
        """Calls are unavailable."""
        raise VideoUnavailableError

    def session_pass(self, request: PassRequest, now: datetime) -> SessionPass:
        """Calls are unavailable."""
        raise VideoUnavailableError

    def verify_webhook(self, body: bytes, authorization: str | None) -> SfuWebhook:
        """Nothing can be verified without the secret."""
        raise WebhookRejectedError

    async def record(self, room_name: str, target: BucketTarget) -> str:
        """Calls are unavailable."""
        raise VideoUnavailableError

    async def stop_egress(self, egress_id: str) -> None:
        """Calls are unavailable."""
        raise VideoUnavailableError

    async def egresses(
        self, room_name: str | None = None, *, active: bool = True
    ) -> Sequence[EgressReport]:
        """Calls are unavailable."""
        raise VideoUnavailableError

    async def egress(self, egress_id: str) -> EgressReport | None:
        """Calls are unavailable."""
        raise VideoUnavailableError

    async def ping(self) -> None:
        """Calls are unavailable."""
        raise VideoUnavailableError
