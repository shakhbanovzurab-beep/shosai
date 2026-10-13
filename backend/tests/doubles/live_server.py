"""A local WebSocket server over TLS that plays a live provider, for the live adapters' tests.

Both adapters connect to it as to the provider: OpenAI's over `wss://` with our socket
library, Gemini's through google-genai, which always speaks TLS. A test gives the server a
scenario — a coroutine that receives the connection — and reads what the client sent.
"""

import asyncio
import datetime
import ipaddress
import json
import ssl
import tempfile
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from websockets.asyncio.server import ServerConnection, serve
from websockets.datastructures import Headers
from websockets.http11 import Request, Response

type Json = dict[str, Any]
type Scenario = Callable[[ServerConnection, "LiveServer"], Awaitable[None]]


@cache
def certificate() -> tuple[bytes, bytes]:
    """A self-signed certificate of 127.0.0.1 and its key, as PEM; one per test run."""
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "127.0.0.1")])
    now = datetime.datetime.now(datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]),
            critical=False,
        )
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    key_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    return cert.public_bytes(serialization.Encoding.PEM), key_pem


def server_tls() -> ssl.SSLContext:
    """The server's TLS context with the test certificate."""
    cert, key = certificate()
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    with tempfile.TemporaryDirectory() as folder:
        cert_file, key_file = Path(folder) / "cert.pem", Path(folder) / "key.pem"
        cert_file.write_bytes(cert)
        key_file.write_bytes(key)
        context.load_cert_chain(cert_file, key_file)
    return context


def client_tls() -> ssl.SSLContext:
    """A client TLS context that trusts only the test certificate."""
    return ssl.create_default_context(cadata=certificate()[0].decode("ascii"))


@dataclass
class LiveServer:
    """What the server saw: handshakes' paths and headers, and every message, parsed."""

    url: str = ""
    handshakes: list[tuple[str, Headers]] = field(default_factory=list)
    received: list[Json] = field(default_factory=list)
    refuse_with: int | None = None
    changed: asyncio.Condition = field(default_factory=asyncio.Condition)

    def of_type(self, kind: str) -> list[Json]:
        """Messages whose `type` is `kind` (OpenAI) or that carry the key `kind` (Gemini)."""
        return [m for m in self.received if m.get("type") == kind or kind in m]

    def keyed(self, kind: str) -> list[Json]:
        """The bodies of messages under the key `kind`, written in snake_case or camelCase."""
        snake = "".join(f"_{c.lower()}" if c.isupper() else c for c in kind)
        return [m.get(kind) or m[snake] for m in self.received if kind in m or snake in m]

    async def receive(self, connection: ServerConnection) -> Json:
        """The next message from the client, recorded."""
        message = json.loads(await connection.recv())
        assert isinstance(message, dict)
        async with self.changed:
            self.received.append(message)
            self.changed.notify_all()
        return message

    async def until(self, check: Callable[[LiveServer], bool]) -> None:
        """Wait, 5 s at most, until what the server received passes the check."""
        async with asyncio.timeout(5), self.changed:
            await self.changed.wait_for(lambda: check(self))


@asynccontextmanager
async def live_server(scenario: Scenario) -> AsyncIterator[LiveServer]:
    """A server on a free port of 127.0.0.1 that runs the scenario for each connection."""
    state = LiveServer()

    def handshake(connection: ServerConnection, request: Request) -> Response | None:
        state.handshakes.append((request.path, request.headers))
        if state.refuse_with is not None:
            return connection.respond(state.refuse_with, "refused by the scenario\n")
        return None

    async def handle(connection: ServerConnection) -> None:
        await scenario(connection, state)

    async with serve(
        handle, "127.0.0.1", 0, ssl=server_tls(), process_request=handshake, compression=None
    ) as server:
        port = next(iter(server.sockets)).getsockname()[1]
        state.url = f"wss://127.0.0.1:{port}"
        yield state
