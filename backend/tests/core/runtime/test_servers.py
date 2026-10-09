"""HTTP servers of a process: started on their socket, drained on stop, signals left alone."""

import asyncio
import signal
import socket
from datetime import timedelta

import httpx
import pytest
from fastapi import FastAPI

from shosai.core.runtime.servers import EDGE_KEEP_ALIVE, HttpServer, server_config

LOOPBACK = "127.0.0.1"
DRAIN = timedelta(seconds=5)


def slow_app(started: asyncio.Event) -> FastAPI:
    """An app with one slow route, to catch a request in flight."""
    app = FastAPI()

    @app.get("/slow")
    async def slow() -> dict[str, str]:
        started.set()
        await asyncio.sleep(0.3)
        return {"status": "done"}

    return app


async def test_stop_lets_the_request_in_flight_finish_and_refuses_new_connections() -> None:
    started = asyncio.Event()
    config = server_config(slow_app(started), trusted_proxies=None, drain=DRAIN)
    server = HttpServer("probe", config, LOOPBACK, 0)
    port = await server.start()

    async with httpx.AsyncClient(base_url=f"http://{LOOPBACK}:{port}", timeout=5) as client:
        in_flight = asyncio.create_task(client.get("/slow"))
        await started.wait()
        await server.stop()
        response = await in_flight
        with pytest.raises(httpx.ConnectError):
            await client.get("/slow")

    assert (response.status_code, response.json()) == (200, {"status": "done"})
    assert server.task.done()


async def test_a_taken_port_is_an_error_at_start() -> None:
    with socket.create_server((LOOPBACK, 0)) as taken:
        port = taken.getsockname()[1]
        config = server_config(FastAPI(), trusted_proxies=None, drain=DRAIN)

        with pytest.raises(OSError, match="in use"):
            await HttpServer("probe", config, LOOPBACK, port).start()


async def test_the_server_leaves_the_stop_signals_to_the_process() -> None:
    before = {stop: signal.getsignal(stop) for stop in (signal.SIGTERM, signal.SIGINT)}
    server = HttpServer(
        "probe", server_config(FastAPI(), trusted_proxies=None, drain=DRAIN), LOOPBACK, 0
    )

    await server.start()
    during = {stop: signal.getsignal(stop) for stop in before}
    await server.stop()

    assert during == before


def test_a_public_server_trusts_exactly_the_configured_proxies() -> None:
    nobody = server_config(FastAPI(), trusted_proxies=[], drain=DRAIN)
    edge = server_config(FastAPI(), trusted_proxies=["10.20.0.0/16"], drain=DRAIN)
    ops = server_config(FastAPI(), trusted_proxies=None, drain=DRAIN)

    # Пустой список — никому, а не умолчание uvicorn «127.0.0.1,::1».
    assert (nobody.proxy_headers, nobody.forwarded_allow_ips) == (True, [])
    assert edge.forwarded_allow_ips == ["10.20.0.0/16"]
    assert ops.proxy_headers is False


def test_the_server_writes_no_access_lines_and_keeps_the_logging_setup() -> None:
    config = server_config(FastAPI(), trusted_proxies=None, drain=DRAIN)

    assert (config.access_log, config.log_config, config.server_header) == (False, None, False)
    assert (config.lifespan, config.ws, config.timeout_graceful_shutdown) == ("off", "none", 5)


def test_a_public_server_keeps_idle_connections_longer_than_the_edge() -> None:
    public = server_config(FastAPI(), trusted_proxies=[], drain=DRAIN, keep_alive=EDGE_KEEP_ALIVE)
    ops = server_config(FastAPI(), trusted_proxies=None, drain=DRAIN)

    assert (public.timeout_keep_alive, ops.timeout_keep_alive) == (75, 5)
