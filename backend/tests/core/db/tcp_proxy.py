"""A TCP proxy in front of a home's PgBouncer for the database tests.

It counts request turns — a burst of bytes from the client after the server spoke — which
is the number of round trips the client waited for. Without an upstream it accepts and
drops every connection, as a home out of reach does; an upstream can be set later.
"""

import asyncio
import contextlib
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlsplit

from pydantic import SecretStr

LOOPBACK = "127.0.0.1"
CHUNK_BYTES = 65536


@dataclass(frozen=True, slots=True)
class Upstream:
    """Where the proxy forwards to."""

    host: str
    port: int


def through(url: SecretStr, port: int) -> SecretStr:
    """The same database address with the host and port of a proxy on loopback."""
    parts = urlsplit(url.get_secret_value())
    credentials = parts.netloc.rsplit("@", 1)[0]
    return SecretStr(parts._replace(netloc=f"{credentials}@{LOOPBACK}:{port}").geturl())


class CountingProxy:
    """Forwards client connections to an upstream and counts the client's request turns."""

    def __init__(self, upstream: Upstream | None) -> None:
        self.upstream = upstream
        self.turns = 0
        self._client_spoke_last = False
        self._server: asyncio.Server | None = None
        self._pipes: set[asyncio.Task[None]] = set()

    async def start(self) -> int:
        """Listen on a free loopback port and return it."""
        self._server = await asyncio.start_server(self._serve, LOOPBACK, 0)
        return int(self._server.sockets[0].getsockname()[1])

    async def stop(self) -> None:
        """Stop listening and cut every forwarded connection."""
        if self._server is not None:
            self._server.close()
        for task in self._pipes:
            task.cancel()
        await asyncio.gather(*self._pipes, return_exceptions=True)
        if self._server is not None:
            await self._server.wait_closed()

    async def cut(self) -> None:
        """Cut every forwarded connection and drop new ones, as a home that went away does."""
        self.upstream = None
        for task in self._pipes:
            task.cancel()
        await asyncio.gather(*self._pipes, return_exceptions=True)

    def reset(self) -> None:
        """Start counting from zero; the next client message opens a new turn."""
        self.turns = 0
        self._client_spoke_last = False

    async def _serve(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        upstream = self.upstream
        if upstream is None:
            writer.close()
            return
        up_reader, up_writer = await asyncio.open_connection(upstream.host, upstream.port)
        for task in (
            asyncio.create_task(self._pipe(reader, up_writer, self._client_sent)),
            asyncio.create_task(self._pipe(up_reader, writer, self._server_sent)),
        ):
            self._pipes.add(task)
            task.add_done_callback(self._pipes.discard)

    def _client_sent(self) -> None:
        if not self._client_spoke_last:
            self.turns += 1
        self._client_spoke_last = True

    def _server_sent(self) -> None:
        self._client_spoke_last = False

    @staticmethod
    async def _pipe(
        reader: asyncio.StreamReader, writer: asyncio.StreamWriter, on_data: Callable[[], None]
    ) -> None:
        try:
            while data := await reader.read(CHUNK_BYTES):
                on_data()
                writer.write(data)
                await writer.drain()
        except ConnectionError:
            # Обрыв с любой стороны — штатный конец пересылки: вторая половина закроется сама.
            return
        finally:
            writer.close()
            # Сокет, уже закрытый другой стороной, при закрытии сообщает о сбросе — это норма.
            with contextlib.suppress(ConnectionError):
                await writer.wait_closed()
