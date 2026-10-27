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
import base64
import binascii
import hashlib
import hmac
from collections.abc import AsyncIterator, Awaitable, Collection, Mapping, Sequence
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Final

import aiohttp
import jwt
import structlog
from livekit.api.access_token import AccessToken, TokenVerifier, VideoGrants
from livekit.api.livekit_api import LiveKitAPI
from livekit.api.twirp_client import ServerError
from livekit.protocol.room import (
    CreateRoomRequest,
    DeleteRoomRequest,
    ListParticipantsRequest,
    ListRoomsRequest,
    RoomParticipantIdentity,
    UpdateParticipantRequest,
    UpdateRoomMetadataRequest,
)
from pydantic import ValidationError

from shosai.features.meetings.application.video_server import (
    PassRequest,
    RoomSpec,
    SessionPass,
    SfuParticipant,
    SfuRoom,
    SfuWebhook,
    VideoServer,
    VideoUnavailableError,
    WebhookRejectedError,
)
from shosai.features.meetings.domain.calls import DEPARTURE_TIMEOUT, EMPTY_TIMEOUT
from shosai.features.meetings.domain.joining import LIVEKIT_TOKEN_TTL
from shosai.features.meetings.infrastructure.livekit_metrics import LiveKitMetrics
from shosai.features.meetings.infrastructure.livekit_wire import (
    participant_of,
    room_of,
    webhook_of,
)
from shosai.features.meetings.infrastructure.unconfigured_server import (
    UnconfiguredVideoServer,
)
from shosai.features.meetings.settings import LiveKitSettings

CALL_TIMEOUT: Final = aiohttp.ClientTimeout(total=5)
NOT_FOUND: Final = "not_found"
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
        try:
            await self._call("set_metadata", self._client.room.update_room_metadata(request))
        except ServerError as error:
            if error.code == NOT_FOUND:
                return False
            raise
        return True

    async def remove_participant(self, room_name: str, identity: str) -> bool:
        """Disconnect a session; False when it is no longer in the room."""
        request = RoomParticipantIdentity(room=room_name, identity=identity)
        try:
            await self._call("remove_participant", self._client.room.remove_participant(request))
        except ServerError as error:
            if error.code == NOT_FOUND:
                return False
            raise
        return True

    async def set_attributes(
        self, room_name: str, identity: str, attributes: Mapping[str, str]
    ) -> bool:
        """Set a session's attributes, an empty value removing one; False when it is gone."""
        request = UpdateParticipantRequest(
            room=room_name, identity=identity, attributes=dict(attributes)
        )
        try:
            await self._call("set_attributes", self._client.room.update_participant(request))
        except ServerError as error:
            if error.code == NOT_FOUND:
                return False
            raise
        return True

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
        token = (authorization or "").removeprefix(BEARER).strip()
        try:
            claims = self._verifier.verify(token)
            claimed = base64.b64decode(claims.sha256 or "", validate=True)
        except (jwt.PyJWTError, binascii.Error) as error:
            raise self._rejected(type(error).__qualname__) from error
        if not claimed or not hmac.compare_digest(hashlib.sha256(body).digest(), claimed):
            raise self._rejected("body_hash_mismatch")
        try:
            webhook = webhook_of(body)
        except ValidationError as error:
            raise self._rejected(type(error).__qualname__) from error
        self._metrics.webhook_verified(accepted=True)
        return webhook

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

    @staticmethod
    def _since(started: float) -> float:
        return asyncio.get_running_loop().time() - started

    def _failed(self, operation: str, started: float, outcome: str, reason: str) -> None:
        self._metrics.called(operation, outcome, self._since(started))
        log.warning(
            "LiveKit не выполнил вызов", operation=operation, outcome=outcome, reason=reason
        )

    def _rejected(self, reason: str) -> WebhookRejectedError:
        self._metrics.webhook_verified(accepted=False)
        log.warning("Вебхук LiveKit отклонён", reason=reason)
        return WebhookRejectedError()


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
