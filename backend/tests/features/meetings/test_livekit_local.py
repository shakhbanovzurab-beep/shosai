"""LiveKit's adapter against the local server of `--profile meetings` (meetings A2, §3.6).

The tests read only `TEST_LIVEKIT_*` (ADR 0009) and are skipped without them: the profile
runs in meetings sessions only (MR-D14); CI sets them. A test client joins through the
signalling WebSocket, which is what a browser does before its media flows. Every room a test
creates is deleted at its end.
"""

import os
import secrets
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Final

import aiohttp
import pytest
from livekit.api.livekit_api import LiveKitAPI
from livekit.protocol.room import ListParticipantsRequest
from livekit.protocol.rtc import SignalResponse
from prometheus_client import CollectorRegistry
from pydantic import SecretStr

from shosai.features.meetings.application.video_server import (
    PassRequest,
    RoomSpec,
    SessionPass,
    VideoServer,
    VideoUnavailableError,
)
from shosai.features.meetings.domain.broadcasts import AUDIENCE, ON_STAGE, SPEAKERS_MAX, VIEWERS_MAX
from shosai.features.meetings.domain.joining import IN_CALL, Grants
from shosai.features.meetings.domain.principals import Principal, new_identity
from shosai.features.meetings.infrastructure.livekit_metrics import LiveKitMetrics
from shosai.features.meetings.infrastructure.livekit_server import open_video_server
from shosai.features.meetings.settings import LiveKitSettings

VARIABLES: Final = ("TEST_LIVEKIT_URL", "TEST_LIVEKIT_API_URL", "TEST_LIVEKIT_API_KEY")
SECRET_VARIABLE: Final = "TEST_LIVEKIT_API_SECRET"
SIGNAL_TIMEOUT: Final = 5.0


def local_settings() -> LiveKitSettings:
    if not all(os.environ.get(name) for name in (*VARIABLES, SECRET_VARIABLE)):
        pytest.skip("локальный LiveKit не задан: TEST_LIVEKIT_* (.env.example, раздел 3)")
    return LiveKitSettings(
        livekit_url=os.environ["TEST_LIVEKIT_URL"],  # type: ignore[arg-type]
        livekit_api_url=os.environ["TEST_LIVEKIT_API_URL"],  # type: ignore[arg-type]
        livekit_api_key=os.environ["TEST_LIVEKIT_API_KEY"],
        livekit_api_secret=SecretStr(os.environ[SECRET_VARIABLE]),
    )


@pytest.fixture
async def sfu() -> AsyncIterator[VideoServer]:
    async with open_video_server(local_settings(), LiveKitMetrics(CollectorRegistry())) as server:
        yield server


@pytest.fixture
async def room_name(sfu: VideoServer) -> AsyncIterator[str]:
    name = f"r-{secrets.token_hex(8)}"
    yield name
    await sfu.delete_room(name)


def guest_pass(sfu: VideoServer, room_name: str) -> SessionPass:
    return sfu.session_pass(
        PassRequest(
            room_name=room_name,
            identity=new_identity(Principal.new_guest()),
            name="Гость",
            grants=IN_CALL,
            attributes={"device.client": "web"},
        ),
        datetime.now(UTC),
    )


async def join(http: aiohttp.ClientSession, issued: SessionPass) -> aiohttp.ClientWebSocketResponse:
    return await http.ws_connect(f"{issued.url}/rtc?access_token={issued.token}&protocol=16")


async def test_a_room_is_created_once_with_its_ceiling_and_metadata(
    sfu: VideoServer, room_name: str
) -> None:
    created = await sfu.create_room(
        RoomSpec(name=room_name, max_participants=4, metadata='{"v":1}')
    )
    again = await sfu.create_room(RoomSpec(name=room_name, max_participants=4, metadata='{"v":1}'))

    assert (created.name, created.metadata) == (room_name, '{"v":1}')
    assert again.sid == created.sid
    assert [room.sid for room in await sfu.rooms([room_name])] == [created.sid]
    await sfu.ping()


async def test_a_client_joins_with_its_pass_and_is_listed_with_its_attributes(
    sfu: VideoServer, room_name: str
) -> None:
    await sfu.create_room(RoomSpec(name=room_name, max_participants=4, metadata="{}"))
    issued = guest_pass(sfu, room_name)

    async with aiohttp.ClientSession() as http, await join(http, issued) as socket:
        first = await socket.receive(timeout=SIGNAL_TIMEOUT)
        answer = SignalResponse.FromString(first.data)
        assert answer.WhichOneof("message") == "join"
        present = await sfu.participants(room_name)

    assert [(person.name, dict(person.attributes)) for person in present] == [
        ("Гость", {"device.client": "web"})
    ]


async def test_a_deleted_room_is_not_revived_by_a_still_valid_pass(
    sfu: VideoServer, room_name: str
) -> None:
    await sfu.create_room(RoomSpec(name=room_name, max_participants=4, metadata="{}"))
    issued = guest_pass(sfu, room_name)
    await sfu.delete_room(room_name)
    await sfu.delete_room(room_name)

    assert await sfu.rooms([room_name]) == []
    assert await sfu.participants(room_name) == []
    async with aiohttp.ClientSession() as http:
        with pytest.raises(aiohttp.WSServerHandshakeError) as refused:
            await join(http, issued)
    # auto_create выключен: комнату создаёт только сервер, пропуск её не воскрешает.
    assert refused.value.status == 404


async def test_an_unreachable_sfu_is_video_unavailable() -> None:
    settings = local_settings().model_copy(update={"livekit_api_url": "http://127.0.0.1:9"})

    async with open_video_server(settings, LiveKitMetrics(CollectorRegistry())) as sfu:
        with pytest.raises(VideoUnavailableError):
            await sfu.ping()


async def test_metadata_attributes_and_removal_reach_a_joined_session(
    sfu: VideoServer, room_name: str
) -> None:
    await sfu.create_room(RoomSpec(name=room_name, max_participants=4, metadata="{}"))
    issued = guest_pass(sfu, room_name)

    async with aiohttp.ClientSession() as http, await join(http, issued) as socket:
        await socket.receive(timeout=SIGNAL_TIMEOUT)
        identity = (await sfu.participants(room_name))[0].identity
        assert await sfu.set_metadata(room_name, '{"v":1}')
        assert await sfu.set_attributes(room_name, identity, {"hand": "2026-10-27T12:00:00Z"})
        attributes = (await sfu.participants(room_name))[0].attributes
        assert attributes["hand"] == "2026-10-27T12:00:00Z"
        assert await sfu.set_attributes(room_name, identity, {"hand": ""})
        assert "hand" not in (await sfu.participants(room_name))[0].attributes
        assert await sfu.remove_participant(room_name, identity)
        assert not await sfu.remove_participant(room_name, identity)
    assert [room.metadata for room in await sfu.rooms([room_name])] == ['{"v":1}']
    assert not await sfu.set_metadata("r-00000000deadbeef", "{}")


async def test_a_reliable_packet_reaches_the_room_and_a_missing_room_is_unavailable(
    sfu: VideoServer, room_name: str
) -> None:
    await sfu.create_room(RoomSpec(name=room_name, max_participants=4, metadata="{}"))

    assert await sfu.publish(room_name, "chat", b'{"v":1}')
    # LiveKit отвечает 503 «no response from servers» на комнату, которой нет ни на одном узле.
    with pytest.raises(VideoUnavailableError):
        await sfu.publish("r-00000000deadbeef", "chat", b'{"v":1}')


def staged_pass(sfu: VideoServer, room_name: str, grants: Grants) -> SessionPass:
    """A broadcast session's pass with its part's rights."""
    request = PassRequest(room_name, new_identity(Principal.new_guest()), "Гость", grants)
    return sfu.session_pass(request, datetime.now(UTC))


async def permissions(room_name: str) -> dict[str, tuple[bool, bool]]:
    """Each session's `hidden` and `can_publish`, as LiveKit itself reports them."""
    settings = local_settings()
    api = LiveKitAPI(
        str(settings.livekit_api_url), settings.livekit_api_key, os.environ[SECRET_VARIABLE]
    )
    try:
        answer = await api.room.list_participants(ListParticipantsRequest(room=room_name))
    finally:
        await api.aclose()
    return {
        item.identity: (item.permission.hidden, item.permission.can_publish)
        for item in answer.participants
    }


async def test_a_broadcasts_audience_is_hidden_and_a_viewer_steps_onto_the_stage_in_session(
    sfu: VideoServer, room_name: str
) -> None:
    await sfu.create_room(RoomSpec(room_name, VIEWERS_MAX + SPEAKERS_MAX + 1, "{}"))
    viewers = [staged_pass(sfu, room_name, AUDIENCE) for _ in range(3)]
    host = staged_pass(sfu, room_name, ON_STAGE)

    async with aiohttp.ClientSession() as http:
        sockets = [await join(http, issued) for issued in viewers]
        try:
            for socket in sockets:
                await socket.receive(timeout=SIGNAL_TIMEOUT)
            async with await join(http, host) as host_socket:
                first = await host_socket.receive(timeout=SIGNAL_TIMEOUT)
                answer = SignalResponse.FromString(first.data)
                listed = [person.identity for person in await sfu.participants(room_name)]
                own = answer.join.participant.identity
                viewer = next(identity for identity in listed if identity != own)
                before = await permissions(room_name)
                stepped = await sfu.set_grants(room_name, viewer, ON_STAGE)
                after = await permissions(room_name)
        finally:
            for socket in sockets:
                await socket.close()

    assert len(listed) == 4
    assert list(answer.join.other_participants) == []
    assert sorted(before.values()) == [(False, True), (True, False), (True, False), (True, False)]
    assert stepped
    assert after[viewer] == (False, True)
