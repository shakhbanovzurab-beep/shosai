"""The WS gateway's sockets on a real uvicorn: origin, hello, capacity, errors and the drain."""

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Final

import pytest
from fastapi import FastAPI, WebSocket
from prometheus_client import CollectorRegistry
from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed, InvalidStatus
from websockets.typing import Origin

from shosai.core.config.loading import load_settings
from shosai.core.runtime.servers import HttpServer, server_config
from shosai.core.web.sockets import (
    GatewaySocket,
    SocketClose,
    SocketGateway,
    SocketMetrics,
    SocketRefusedError,
    close_code_for,
    socket_gateway,
)
from tests.core.config.sample_environ import local_environ
from tests.harness.process_environ import LOOPBACK, loopback_socket

CABINET: Final = Origin("https://shosai.example")
STRANGER: Final = Origin("https://evil.example")
GOOD_TOKEN: Final = "good-token"
DRAIN: Final = timedelta(seconds=5)
BAD: Final = SocketClose.BAD_HELLO


async def session(socket: GatewaySocket) -> None:
    """Hello with a known token, then the size of every frame until the client goes."""
    hello = await socket.hello()
    if hello.token != GOOD_TOKEN:
        raise SocketRefusedError(close_code_for(401), "token_invalid")
    if hello.fields.get("fail"):
        message = "сбой сессии в тесте"
        raise RuntimeError(message)
    await socket.send_json(
        {"type": "ready", "v": hello.version, "scope": hello.fields.get("scope")}
    )
    async for frame in socket.frames():
        await socket.send_json({"type": "got", "size": len(frame)})


@asynccontextmanager
async def gateway_server(gateway: SocketGateway) -> AsyncIterator[str]:
    """A server whose one route is a gateway socket; its address."""
    app = FastAPI()

    @app.websocket("/v1/ws/probe")
    async def probe(websocket: WebSocket) -> None:
        await gateway.serve(websocket, "/v1/ws/probe", session)

    config = server_config(app, trusted_proxies=None, drain=DRAIN, websockets=True)
    server = HttpServer("ws-probe", config, LOOPBACK, 0)
    port = await server.start()
    try:
        yield loopback_socket(port, "/v1/ws/probe")
    finally:
        await server.stop()


def gateway_of(
    capacity: int = 4, hello_within: float = 5.0
) -> tuple[SocketGateway, CollectorRegistry]:
    registry = CollectorRegistry()
    origins = frozenset({str(CABINET)})
    metrics = SocketMetrics(registry)
    return SocketGateway(origins, capacity, metrics, timedelta(seconds=hello_within)), registry


def closed(registry: CollectorRegistry, code: int) -> float:
    value = registry.get_sample_value(
        "shosai_ws_sockets_closed_total", {"route": "/v1/ws/probe", "code": str(code)}
    )
    return value or 0.0


async def hello(client: ClientConnection, token: str = GOOD_TOKEN, **fields: object) -> None:
    await client.send(json.dumps({"type": "hello", "v": 1, "token": token, **fields}))


async def close_code(client: ClientConnection) -> int | None:
    with pytest.raises(ConnectionClosed):
        await asyncio.wait_for(client.recv(), 5)
    return client.close_code


async def test_a_session_reads_hello_and_the_frames_that_follow() -> None:
    gateway, registry = gateway_of()
    async with gateway_server(gateway) as url, connect(url, origin=CABINET) as client:
        await hello(client, scope={"kind": "personal"})
        ready = json.loads(await client.recv())
        await client.send(b"\x00\x01" * 640)
        got = json.loads(await client.recv())
        await client.send("text")
        text = json.loads(await client.recv())
        await client.close()
        await asyncio.sleep(0.1)

    assert ready == {"type": "ready", "v": 1, "scope": {"kind": "personal"}}
    assert (got, text) == ({"type": "got", "size": 1280}, {"type": "got", "size": 4})
    assert closed(registry, SocketClose.NORMAL) == 1
    assert gateway.open_count == 0


async def test_another_origin_is_refused_before_the_handshake_ends() -> None:
    gateway, registry = gateway_of()
    async with gateway_server(gateway) as url:
        with pytest.raises(InvalidStatus) as refused:
            async with connect(url, origin=STRANGER):
                pass
        with pytest.raises(InvalidStatus):
            async with connect(url):
                pass

    assert refused.value.response.status_code == 403
    assert closed(registry, SocketClose.FORBIDDEN) == 2


@pytest.mark.parametrize(
    ("first", "code", "reason"),
    [
        ("not json", SocketClose.BAD_HELLO, "bad_hello"),
        (json.dumps({"type": "hello", "v": "1", "token": GOOD_TOKEN}), BAD, "bad_hello"),
        (json.dumps({"type": "hi", "v": 1, "token": GOOD_TOKEN}), BAD, "bad_hello"),
        (b"\x00\x00", SocketClose.BAD_HELLO, "bad_hello"),
        (json.dumps({"type": "hello", "v": 1, "token": "stolen"}), 4401, "token_invalid"),
    ],
)  # fmt: skip
async def test_a_wrong_hello_or_token_ends_the_socket_with_its_code_and_reason(
    first: str | bytes, code: int, reason: str
) -> None:
    gateway, registry = gateway_of()
    async with gateway_server(gateway) as url, connect(url, origin=CABINET) as client:
        await client.send(first)
        received = await close_code(client)

    assert (received, client.close_reason) == (code, reason)
    assert closed(registry, code) == 1


async def test_a_late_hello_ends_the_socket_with_4408() -> None:
    gateway, _ = gateway_of(hello_within=0.2)
    async with gateway_server(gateway) as url, connect(url, origin=CABINET) as client:
        assert await close_code(client) == SocketClose.HELLO_TIMEOUT


async def test_a_full_process_closes_one_more_socket_with_1013() -> None:
    gateway, registry = gateway_of(capacity=1)
    async with gateway_server(gateway) as url, connect(url, origin=CABINET) as first:
        await hello(first)
        await first.recv()
        async with connect(url, origin=CABINET) as second:
            assert await close_code(second) == SocketClose.TRY_LATER
        assert gateway.open_count == 1

    assert closed(registry, SocketClose.TRY_LATER) == 1


async def test_a_failing_session_ends_with_1011() -> None:
    gateway, _ = gateway_of()
    async with gateway_server(gateway) as url, connect(url, origin=CABINET) as client:
        await hello(client, fail=True)
        assert await close_code(client) == SocketClose.INTERNAL


async def test_the_drain_says_server_shutdown_and_closes_who_stays_with_1012() -> None:
    gateway, registry = gateway_of()
    async with (
        gateway_server(gateway) as url,
        connect(url, origin=CABINET) as leaving,
        connect(url, origin=CABINET) as staying,
    ):
        for client in (leaving, staying):
            await hello(client)
            await client.recv()
        drain = asyncio.create_task(gateway.drain(timedelta(seconds=0.5)))
        notices = [json.loads(await client.recv()) for client in (leaving, staying)]
        await leaving.close()
        await drain
        stayed = await close_code(staying)

    assert notices == [{"type": "server.shutdown"}] * 2
    assert stayed == SocketClose.RESTART
    # Оба закончились из-за остановки: ушедший сам после server.shutdown — тоже.
    assert closed(registry, SocketClose.RESTART) == 2
    assert gateway.open_count == 0


async def test_without_websockets_a_server_refuses_the_upgrade() -> None:
    app = FastAPI()
    server = HttpServer(
        "api-probe", server_config(app, trusted_proxies=None, drain=DRAIN), LOOPBACK, 0
    )
    port = await server.start()
    try:
        with pytest.raises(InvalidStatus):
            async with connect(loopback_socket(port, "/v1/ws/probe"), origin=CABINET):
                pass
    finally:
        await server.stop()


def test_the_gateway_trusts_the_cabinet_and_the_cors_allowlist() -> None:
    settings = load_settings(
        local_environ(
            PUBLIC_BASE_URL="https://cabinet.example/",
            CORS_ALLOWED_ORIGINS="http://localhost:3000",
            WS_SOCKETS_PER_PROCESS="3",
        )
    )

    gateway = socket_gateway(settings, CollectorRegistry())

    assert gateway.trusts("https://cabinet.example")
    assert gateway.trusts("http://localhost:3000")
    assert not gateway.trusts("https://evil.example")
    assert gateway.capacity == 3
