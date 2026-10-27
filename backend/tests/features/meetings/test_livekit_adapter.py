"""LiveKit's adapter without a server: passes, webhook signatures and failures (meetings A2)."""

import base64
import hashlib
import json
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast

import aiohttp
import jwt
import pytest
from livekit.api.access_token import AccessToken
from livekit.api.livekit_api import LiveKitAPI
from livekit.api.twirp_client import ServerError
from prometheus_client import CollectorRegistry
from pydantic import SecretStr

from shosai.features.meetings.application.video_server import (
    PassRequest,
    RoomSpec,
    VideoUnavailableError,
    WebhookKind,
    WebhookRejectedError,
)
from shosai.features.meetings.domain.broadcasts import AUDIENCE
from shosai.features.meetings.domain.joining import IN_CALL
from shosai.features.meetings.infrastructure.livekit_metrics import LiveKitMetrics
from shosai.features.meetings.infrastructure.livekit_server import (
    LiveKitServer,
    UnconfiguredVideoServer,
)
from shosai.features.meetings.settings import LiveKitSettings

KEY = "APItest"
SECRET = "test-secret-of-at-least-thirty-two-characters"
NOW = datetime(2026, 10, 27, 12, tzinfo=UTC)
SETTINGS = LiveKitSettings(
    livekit_url="wss://rtc.shosai.tech",  # type: ignore[arg-type]
    livekit_api_url="http://livekit:7880",  # type: ignore[arg-type]
    livekit_api_key=KEY,
    livekit_api_secret=SecretStr(SECRET),
)
BODY = json.dumps(
    {
        "event": "participant_joined",
        "id": "EV_1",
        "createdAt": "1793102400",
        "room": {"sid": "RM_1", "name": "r-0011223344556677", "numParticipants": 2},
        "participant": {"identity": "guest-0123456789ab__0a1b2c3d"},
    }
).encode()


def server(**room_calls: Callable[..., Awaitable[Any]]) -> LiveKitServer:
    client = SimpleNamespace(room=SimpleNamespace(**room_calls))
    return LiveKitServer(cast("LiveKitAPI", client), SETTINGS, LiveKitMetrics(CollectorRegistry()))


def signed(body: bytes, secret: str = SECRET) -> str:
    digest = base64.b64encode(hashlib.sha256(body).digest()).decode()
    return AccessToken(KEY, secret).with_sha256(digest).to_jwt()


def test_a_pass_carries_the_session_its_rights_and_attributes_for_ten_minutes() -> None:
    issued = server().session_pass(
        PassRequest(
            room_name="r-0011223344556677",
            identity="guest-0123456789ab__0a1b2c3d",
            name="Анна",
            grants=IN_CALL,
            attributes={"device.os": "macos"},
        ),
        NOW,
    )
    claims = jwt.decode(issued.token, SECRET, algorithms=["HS256"], issuer=KEY)

    assert (issued.url, issued.expires_at) == ("wss://rtc.shosai.tech", NOW + timedelta(minutes=10))
    assert claims["sub"] == "guest-0123456789ab__0a1b2c3d"
    assert claims["name"] == "Анна"
    assert claims["attributes"] == {"device.os": "macos"}
    assert claims["exp"] - claims["nbf"] == 600
    video = claims["video"]
    assert video["room"] == "r-0011223344556677"
    assert video["roomJoin"]
    assert video["canPublish"]
    assert video["canPublishData"]
    assert video["canUpdateOwnMetadata"]
    assert not video.get("roomAdmin")
    assert "secret" not in repr(issued)


def test_an_audience_pass_publishes_nothing_and_is_hidden() -> None:
    issued = server().session_pass(
        PassRequest(room_name="r-1", identity="i", name="n", grants=AUDIENCE), NOW
    )
    video = jwt.decode(issued.token, SECRET, algorithms=["HS256"], issuer=KEY)["video"]

    assert not video["canPublish"]
    assert not video["canPublishData"]
    assert video["hidden"]


def test_a_webhook_signed_over_its_body_is_read() -> None:
    webhook = server().verify_webhook(BODY, signed(BODY))

    assert webhook.kind is WebhookKind.PARTICIPANT_JOINED
    assert (webhook.id, webhook.room_name, webhook.room_sid) == (
        "EV_1",
        "r-0011223344556677",
        "RM_1",
    )
    assert (webhook.participants, webhook.identity) == (2, "guest-0123456789ab__0a1b2c3d")
    assert webhook.created_at == datetime.fromtimestamp(1793102400, UTC)
    # Тот же заголовок с префиксом Bearer принимается так же.
    assert server().verify_webhook(BODY, f"Bearer {signed(BODY)}") == webhook


@pytest.mark.parametrize(
    "authorization",
    [
        None,
        "",
        "not-a-token",
        signed(BODY, secret="another-secret-of-thirty-two-characters!"),
        signed(BODY.replace(b"EV_1", b"EV_2")),
        AccessToken(KEY, SECRET).to_jwt(),
    ],
)
def test_a_forged_or_mismatched_webhook_is_rejected(authorization: str | None) -> None:
    with pytest.raises(WebhookRejectedError) as error:
        server().verify_webhook(BODY, authorization)
    assert (error.value.code, error.value.status) == ("webhook_rejected", 401)


def test_an_unknown_webhook_kind_is_kept_as_other() -> None:
    body = json.dumps({"event": "agent_dispatched", "id": "EV_9", "room": {"name": "r-1"}}).encode()

    assert server().verify_webhook(body, signed(body)).kind is WebhookKind.OTHER


async def raising(error: BaseException) -> None:
    raise error


@pytest.mark.parametrize(
    "error",
    [
        aiohttp.ClientConnectionError("refused"),
        TimeoutError(),
        ServerError("unavailable", "down", status=503),
    ],
)
async def test_an_unreachable_or_failing_sfu_is_video_unavailable(error: BaseException) -> None:
    sfu = server(create_room=lambda _request: raising(error))

    with pytest.raises(VideoUnavailableError) as raised:
        await sfu.create_room(RoomSpec(name="r-1", max_participants=4, metadata="{}"))
    assert (raised.value.code, raised.value.status) == ("video_unavailable", 503)


async def test_a_refusal_is_our_bug_and_is_raised_as_it_is() -> None:
    sfu = server(
        create_room=lambda _request: raising(ServerError("invalid_argument", "x", status=400))
    )

    with pytest.raises(ServerError):
        await sfu.create_room(RoomSpec(name="r-1", max_participants=4, metadata="{}"))


async def test_a_room_already_gone_is_deleted_and_has_nobody() -> None:
    gone = ServerError("not_found", "room not found", status=404)
    sfu = server(
        delete_room=lambda _request: raising(gone),
        list_participants=lambda _request: raising(gone),
    )

    await sfu.delete_room("r-1")
    assert await sfu.participants("r-1") == []


async def test_without_livekit_every_call_is_unavailable_and_every_webhook_rejected() -> None:
    sfu = UnconfiguredVideoServer()

    with pytest.raises(VideoUnavailableError):
        await sfu.rooms()
    with pytest.raises(VideoUnavailableError):
        sfu.session_pass(PassRequest(room_name="r", identity="i", name="n", grants=IN_CALL), NOW)
    with pytest.raises(WebhookRejectedError):
        sfu.verify_webhook(BODY, signed(BODY))
    with pytest.raises(ValueError, match="LiveKit"):
        LiveKitServer(
            cast("LiveKitAPI", None), LiveKitSettings(), LiveKitMetrics(CollectorRegistry())
        )
