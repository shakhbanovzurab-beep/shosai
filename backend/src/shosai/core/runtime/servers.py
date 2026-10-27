"""HTTP servers of a process: uvicorn on the process's event loop, stopped in order (§3.11).

A process runs up to two servers: the public app of `api` or `ws` and the ops app of every
role. On SIGTERM the public server stops first — it takes no new connection and lets
in-flight requests finish within the drain time — and the ops server last, so readiness
reports the drain until the end. uvicorn would catch SIGTERM itself and stop every server
at once, so the process handles signals (`signals.py`) and uvicorn's capture is off.

The process binds the socket itself: a busy port is an `OSError` at the start step that
names it, where uvicorn would call `sys.exit`. uvicorn's own logging setup and access
lines are off; the request boundary writes one access line per request (§16.1).
"""

import asyncio
import socket
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import timedelta
from ipaddress import ip_address
from typing import Final

import structlog
import uvicorn
from starlette.types import ASGIApp

# Старт сервера на уже открытом сокете занимает доли секунды; дольше — сбой.
START_TIMEOUT: Final = timedelta(seconds=5)
START_POLL_SECONDS: Final = 0.01
BACKLOG: Final = 2048
DEFAULT_KEEP_ALIVE: Final = timedelta(seconds=5)
# Дольше, чем edge держит простаивающее соединение к процессу (у NGINX по умолчанию 60 с):
# иначе сервер закрывает соединение, которое edge в тот же миг берёт для запроса, — 502.
EDGE_KEEP_ALIVE: Final = timedelta(seconds=75)
# Кадр WebSocket: 40 мс звука — 1–2 КБ, управляющий JSON меньше; больше 64 КБ — ошибка клиента.
WS_MAX_FRAME: Final = 64 * 1024
# Пинг держит соединение через edge и находит пропавших клиентов за 20 + 20 с.
WS_PING: Final = timedelta(seconds=20)
log = structlog.stdlib.get_logger(__name__)


class ServerStoppedError(Exception):
    """The server ended while it was starting."""


class ManagedServer(uvicorn.Server):
    """uvicorn's server without its signal handlers: the process stops it."""

    @contextmanager
    def capture_signals(self) -> Iterator[None]:
        """Leave the signals to the process (`core/runtime/signals.py`)."""
        yield


def server_config(
    app: ASGIApp,
    *,
    trusted_proxies: Sequence[str] | None,
    drain: timedelta,
    keep_alive: timedelta = DEFAULT_KEEP_ALIVE,
    websockets: bool = False,
) -> uvicorn.Config:
    """uvicorn's settings for one server of the process.

    `trusted_proxies` is None for a server behind no proxy (the ops app); a list, even an
    empty one, turns on `X-Forwarded-*` for exactly those peers and nobody else.
    `keep_alive` is how long an idle connection stays open. `websockets` turns WebSocket
    upgrades on — only the WS gateway takes them (ADR 0070).
    """
    return uvicorn.Config(
        app,
        lifespan="off",
        log_config=None,
        access_log=False,
        server_header=False,
        http="h11",
        # WebSocket — библиотека websockets без своего I/O; кадры без сжатия: звук не сжимается,
        # а сжатие стоило бы процессора на каждом кадре.
        ws="websockets-sansio" if websockets else "none",
        ws_max_size=WS_MAX_FRAME,
        ws_per_message_deflate=False,
        ws_ping_interval=WS_PING.total_seconds(),
        ws_ping_timeout=WS_PING.total_seconds(),
        proxy_headers=trusted_proxies is not None,
        forwarded_allow_ips=list(trusted_proxies or ()),
        backlog=BACKLOG,
        timeout_keep_alive=int(keep_alive.total_seconds()),
        timeout_graceful_shutdown=int(drain.total_seconds()),
    )


def bind_socket(host: str, port: int) -> socket.socket:
    """A listening TCP socket on the address; `OSError` when the port is taken."""
    family = socket.AF_INET6 if ip_address(host).version == 6 else socket.AF_INET
    return socket.create_server((host, port), family=family, backlog=BACKLOG)


class HttpServer:
    """One uvicorn server of the process: started on its socket, stopped on request."""

    def __init__(self, name: str, config: uvicorn.Config, host: str, port: int) -> None:
        self.name = name
        self._server = ManagedServer(config)
        self._host = host
        self._port = port
        self._task: asyncio.Task[None] | None = None

    @property
    def task(self) -> asyncio.Task[None]:
        """The task serving connections; it ends when the server stops or fails."""
        if self._task is None:
            message = f"сервер {self.name} не запущен"
            raise RuntimeError(message)
        return self._task

    async def start(self) -> int:
        """Listen on the address and return the bound port once the server accepts."""
        sock = bind_socket(self._host, self._port)
        port = int(sock.getsockname()[1])
        task = asyncio.create_task(self._server.serve(sockets=[sock]), name=f"http:{self.name}")
        self._task = task
        try:
            async with asyncio.timeout(START_TIMEOUT.total_seconds()):
                while not self._server.started:
                    if task.done():
                        await task
                        message = f"сервер {self.name} завершился при старте"
                        raise ServerStoppedError(message)
                    await asyncio.sleep(START_POLL_SECONDS)
        except BaseException:
            task.cancel()
            sock.close()
            raise
        log.info("HTTP-сервер принимает соединения", server=self.name, port=port)
        return port

    async def stop(self) -> None:
        """Stop accepting, let in-flight requests finish within the drain time, then end."""
        task = self.task
        self._server.should_exit = True
        await task
        log.info("HTTP-сервер остановлен", server=self.name)
