"""LiveKit's server API behind meetings' `VideoServer` port (meetings plan A2, §3.3).

The client talks to the server API at its internal address, without a path prefix (the
draft lost a `/livekit` prefix once), and never reads LiveKit's own environment variables:
every value comes from `LIVEKIT_*`. Each call is bounded by 5 s and tried once — the
callers decide whether to retry — and a transport error, a timeout or a 5xx becomes
`VideoUnavailableError`; a 4xx is a bug of ours and is raised as it is. Webhooks are checked
here, not by the SDK's receiver: the JWT is verified with the API's key and secret, and the
body's SHA-256 is compared with the token's claim in constant time.
"""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Collection, Mapping, Sequence
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Final

import aiohttp
import structlog
from livekit.api.access_token import AccessToken, TokenVerifier, VideoGrants
from livekit.api.livekit_api import LiveKitAPI
from livekit.api.twirp_client import ServerError
from livekit.protocol.egress import ListEgressRequest, StopEgressRequest
from livekit.protocol.models import DataPacket
from livekit.protocol.room import (
    CreateRoomRequest,
    DeleteRoomRequest,
    ListParticipantsRequest,
    ListRoomsRequest,
    RoomParticipantIdentity,
    SendDataRequest,
    UpdateParticipantRequest,
    UpdateRoomMetadataRequest,
)

from shosai.features.meetings.application.video_server import (
    BucketTarget,
    EgressReport,
    PassRequest,
    RoomSpec,
    SessionPass,
    SfuParticipant,
    SfuRoom,
    SfuWebhook,
    VideoServer,
    VideoUnavailableError,
)
from shosai.features.meetings.domain.calls import DEPARTURE_TIMEOUT, EMPTY_TIMEOUT
from shosai.features.meetings.domain.joining import LIVEKIT_TOKEN_TTL
from shosai.features.meetings.infrastructure.livekit_egress import composite, report_of
from shosai.features.meetings.infrastructure.livekit_metrics import LiveKitMetrics
from shosai.features.meetings.infrastructure.livekit_signatures import verified_webhook
from shosai.features.meetings.infrastructure.livekit_wire import (
    participant_of,
    room_of,
)
from shosai.features.meetings.infrastructure.unconfigured_server import (
    UnconfiguredVideoServer,
)
from shosai.features.meetings.settings import LiveKitSettings

CALL_TIMEOUT: Final = aiohttp.ClientTimeout(total=5)
NOT_FOUND: Final = "not_found"
# Остановка уже законченного egress: LiveKit отвечает этими кодами, это не сбой.
OVER: Final = frozenset({NOT_FOUND, "failed_precondition"})
FIRST_SERVER_ERROR: Final = 500
BEARER: Final = "Bearer "
PROBE_ROOM: Final = "shosai-probe"
log = structlog.stdlib.get_logger(__name__)


class LiveKitServer:
    """The SFU through LiveKit's Twirp API and its HS256 signatures."""

    def __init__(
        self, client: LiveKitAPI, settings: LiveKitSettings, metrics: LiveKitMetrics
    ) -> None:
        if not settings.configured:
            message = "LiveKit не настроен: адаптер строится только из полных настроек"
            raise ValueError(message)
        self._client = client
        self._metrics = metrics
        # pydantic дописывает «/» к адресу без пути; клиент сам добавит /rtc.
        self._url = str(settings.livekit_url).rstrip("/")
        self._key = settings.livekit_api_key or ""
        secret = settings.livekit_api_secret
        self._secret = secret.get_secret_value() if secret is not None else ""
        self._verifier = TokenVerifier(self._key, self._secret)

    async def create_room(self, spec: RoomSpec) -> SfuRoom:
        """Create the room, or answer the one that already has this name."""
        request = CreateRoomRequest(
            name=spec.name,
            empty_timeout=int(EMPTY_TIMEOUT.total_seconds()),
            departure_timeout=int(DEPARTURE_TIMEOUT.total_seconds()),
            max_participants=spec.max_participants,
            metadata=spec.metadata,
        )
        room = await self._call("create_room", self._client.room.create_room(request))
        return room_of(room)

    async def rooms(self, names: Collection[str] = ()) -> Sequence[SfuRoom]:
        """The rooms the SFU holds, only those named when names are given."""
        request = ListRoomsRequest(names=list(names))
        answer = await self._call("list_rooms", self._client.room.list_rooms(request))
        return [room_of(room) for room in answer.rooms]

    async def delete_room(self, name: str) -> None:
        """End the room for everyone; a room the SFU no longer holds is already gone."""
        try:
            await self._call(
                "delete_room", self._client.room.delete_room(DeleteRoomRequest(room=name))
            )
        except ServerError as error:
            if error.code != NOT_FOUND:
                raise

    async def participants(self, room_name: str) -> Sequence[SfuParticipant]:
        """The sessions in a room; none when the SFU does not hold it."""
        request = ListParticipantsRequest(room=room_name)
        try:
            answer = await self._call(
                "list_participants", self._client.room.list_participants(request)
            )
        except ServerError as error:
            if error.code == NOT_FOUND:
                return []
            raise
        return [participant_of(participant) for participant in answer.participants]

    async def set_metadata(self, room_name: str, metadata: str) -> bool:
        """Replace a room's metadata; False when the SFU no longer holds the room."""
        request = UpdateRoomMetadataRequest(room=room_name, metadata=metadata)
        return await self._found("set_metadata", self._client.room.update_room_metadata(request))

    async def remove_participant(self, room_name: str, identity: str) -> bool:
        """Disconnect a session; False when it is no longer in the room."""
        request = RoomParticipantIdentity(room=room_name, identity=identity)
        return await self._found(
            "remove_participant", self._client.room.remove_participant(request)
        )

    async def publish(self, room_name: str, topic: str, payload: bytes) -> bool:
        """Send a reliable data packet to everyone in the room; False when the SFU lacks it."""
        request = SendDataRequest(
            room=room_name, data=payload, kind=DataPacket.Kind.RELIABLE, topic=topic
        )
        return await self._found("publish", self._client.room.send_data(request))

    async def set_attributes(
        self, room_name: str, identity: str, attributes: Mapping[str, str]
    ) -> bool:
        """Set a session's attributes, an empty value removing one; False when it is gone."""
        request = UpdateParticipantRequest(
            room=room_name, identity=identity, attributes=dict(attributes)
        )
        return await self._found("set_attributes", self._client.room.update_participant(request))

    def session_pass(self, request: PassRequest, now: datetime) -> SessionPass:
        """A pass for one session, valid for the join's 10 minutes."""
        grants = VideoGrants(
            room_join=True,
            room=request.room_name,
            can_publish=request.grants.can_publish,
            can_subscribe=True,
            can_publish_data=request.grants.can_publish_data,
            can_update_own_metadata=request.grants.can_update_own_metadata,
            hidden=request.grants.hidden,
        )
        token = (
            AccessToken(self._key, self._secret)
            .with_identity(request.identity)
            .with_name(request.name)
            .with_ttl(LIVEKIT_TOKEN_TTL)
            .with_grants(grants)
            .with_attributes(dict(request.attributes))
            .to_jwt()
        )
        return SessionPass(token=token, url=self._url, expires_at=now + LIVEKIT_TOKEN_TTL)

    def verify_webhook(self, body: bytes, authorization: str | None) -> SfuWebhook:
        """The webhook if it is signed over this body; `WebhookRejectedError` otherwise."""
        return verified_webhook(self._verifier, self._metrics, body, authorization)

    async def record(self, room_name: str, target: BucketTarget) -> str:
        """Start the room's video recording into the bucket; its egress id."""
        started = await self._call(
            "record", self._client.egress.start_room_composite_egress(composite(room_name, target))
        )
        return started.egress_id

    async def stop_egress(self, egress_id: str) -> None:
        """Stop an egress; one already over is left as it is."""
        try:
            await self._call(
                "stop_egress",
                self._client.egress.stop_egress(StopEgressRequest(egress_id=egress_id)),
            )
        except ServerError as error:
            if error.code not in OVER:
                raise

    async def egresses(
        self, room_name: str | None = None, *, active: bool = True
    ) -> Sequence[EgressReport]:
        """The egresses the SFU runs, a room's only when named; with `active` off, also the
        ones over that the SFU still remembers."""
        request = ListEgressRequest(room_name=room_name or "", active=active)
        answer = await self._call("list_egress", self._client.egress.list_egress(request))
        return [report_of(item) for item in answer.items]

    async def egress(self, egress_id: str) -> EgressReport | None:
        """One egress as the SFU last saw it, running or over; None when it does not know it."""
        request = ListEgressRequest(egress_id=egress_id)
        answer = await self._call("get_egress", self._client.egress.list_egress(request))
        return next((report_of(item) for item in answer.items), None)

    async def ping(self) -> None:
        """Answer when the SFU's API answers; for the readiness probe."""
        # Фильтр по имени, которого нет: ответ пуст, сколько бы комнат ни держал SFU.
        await self._call("ping", self._client.room.list_rooms(ListRoomsRequest(names=[PROBE_ROOM])))

    async def _call[T](self, operation: str, call: Awaitable[T]) -> T:
        started = asyncio.get_running_loop().time()
        try:
            answer = await call
        except (aiohttp.ClientError, TimeoutError) as error:
            self._failed(operation, started, "unreachable", type(error).__qualname__)
            raise VideoUnavailableError from error
        except ServerError as error:
            if error.status >= FIRST_SERVER_ERROR:
                self._failed(operation, started, "server_error", error.code)
                raise VideoUnavailableError from error
            if error.code == NOT_FOUND:
                # Комнаты уже нет — обычный ответ, решает вызывающий; не авария.
                self._metrics.called(operation, NOT_FOUND, self._since(started))
                raise
            self._failed(operation, started, "refused", error.code)
            raise
        self._metrics.called(operation, "ok", self._since(started))
        return answer

    async def _found(self, operation: str, call: Awaitable[object]) -> bool:
        try:
            await self._call(operation, call)
        except ServerError as error:
            if error.code == NOT_FOUND:
                return False
            raise
        return True

    @staticmethod
    def _since(started: float) -> float:
        return asyncio.get_running_loop().time() - started

    def _failed(self, operation: str, started: float, outcome: str, reason: str) -> None:
        self._metrics.called(operation, outcome, self._since(started))
        log.warning(
            "LiveKit не выполнил вызов", operation=operation, outcome=outcome, reason=reason
        )


@asynccontextmanager
async def open_video_server(
    settings: LiveKitSettings, metrics: LiveKitMetrics
) -> AsyncIterator[VideoServer]:
    """The SFU for the process's life: its HTTP session is closed when the process stops."""
    if not settings.configured:
        log.info("LiveKit не настроен: звонки отвечают 503 video_unavailable")
        yield UnconfiguredVideoServer()
        return
    secret = settings.livekit_api_secret
    client = LiveKitAPI(
        str(settings.livekit_api_url).rstrip("/"),
        settings.livekit_api_key,
        secret.get_secret_value() if secret is not None else None,
        timeout=CALL_TIMEOUT,
        failover=False,
    )
    try:
        yield LiveKitServer(client, settings, metrics)
    finally:
        await client.aclose()
