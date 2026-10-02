"""Dependencies that do not answer, for the outage tests of Valkey, the cache and storage.

A silent server accepts a connection and never replies: it is slower than any deadline.
A closed port refuses the connection at once, as a stopped server does. Neither touches
the shared local services, which other runs use at the same time.
"""

import asyncio
import contextlib
import socket
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from pydantic import SecretStr
from redis.asyncio import Redis

from tests.core.db.tcp_proxy import LOOPBACK, Upstream

CHUNK_BYTES = 65536


@asynccontextmanager
async def silent_server() -> AsyncIterator[int]:
    """The port of a server that reads requests and never answers; stopped on exit."""

    async def swallow(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        # Соединение, закрытое любой стороной, — штатный конец: сервер только молчит.
        try:
            with contextlib.suppress(ConnectionError):
                while await reader.read(CHUNK_BYTES):
                    pass
        finally:
            writer.close()

    server = await asyncio.start_server(swallow, LOOPBACK, 0)
    try:
        yield int(server.sockets[0].getsockname()[1])
    finally:
        server.close()
        server.close_clients()
        await server.wait_closed()


def closed_port() -> int:
    """A loopback port nothing listens on: connecting is refused at once."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind((LOOPBACK, 0))
        return int(probe.getsockname()[1])


def redis_url(port: int) -> SecretStr:
    """A Redis address on loopback for a client that should meet an outage."""
    return SecretStr(f"redis://{LOOPBACK}:{port}/1")


def upstream_of(client: Redis) -> Upstream:
    """Where a client of the slot's database connects, for a proxy in front of it."""
    kwargs = client.connection_pool.connection_kwargs
    return Upstream(str(kwargs["host"]), int(kwargs["port"]))


def through(client: Redis, port: int) -> SecretStr:
    """The same server, password and database index, reached through a loopback proxy."""
    kwargs = client.connection_pool.connection_kwargs
    return SecretStr(f"redis://:{kwargs['password']}@{LOOPBACK}:{port}/{kwargs['db']}")
