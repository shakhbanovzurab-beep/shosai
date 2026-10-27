"""The WS gateway's sockets (ARCHITECTURE §4.2, §4.3, §10; ADR 0070).

A slice's WebSocket route hands its socket to `SocketGateway.serve` with its session:

- the upgrade comes only from the cabinet's origins; another origin is refused before the
  handshake completes (HTTP 403 to the browser);
- a process holds at most `capacity` sockets: one more is accepted and closed at once with
  1013, so the client retries and the edge's least-connection balancing finds another process;
- the session reads `hello` first: a JSON object `{"type": "hello", "v": …, "token": …}` within
  5 s, or the socket closes with 4408 (late) or 4400 (malformed);
- before the process stops, `drain` sends every socket `{"type": "server.shutdown"}`, lets the
  sessions end within the drain time and closes the rest with 1012;
- open sockets, their ends by close code and their lifetimes are metrics by route.

Close codes 4000 to 4999 mirror HTTP: `4000 + status` (4401 for a bad token, 4403 forbidden,
4409 a second session, 4429 a limit); the close reason is the refusal's error code. The token
is checked by the slice through identity's `Authenticator`: core knows no identity.
"""

import asyncio
import contextlib
import json
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from datetime import timedelta
from enum import IntEnum
from typing import Any, Final

import structlog
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram
from starlette.websockets import WebSocket, WebSocketDisconnect, WebSocketState

from shosai.core.config.loading import Settings
from shosai.core.config.values import normalize_origin

HELLO_TIMEOUT: Final = timedelta(seconds=5)
SHUTDOWN_FRAME: Final = {"type": "server.shutdown"}
# Корзины длительности сокета: от отказа на рукопожатии до получасового голосового разговора.
SECONDS_BUCKETS: Final = (1, 5, 15, 60, 300, 900, 1800, 3600, float("inf"))
APPLICATION_CODES: Final = 4000
log = structlog.stdlib.get_logger(__name__)


class SocketClose(IntEnum):
    """Why a socket closed: RFC 6455 codes and the gateway's own, `4000 + HTTP status`."""

    NORMAL = 1000
    INTERNAL = 1011
    RESTART = 1012
    TRY_LATER = 1013
    BAD_HELLO = 4400
    UNAUTHORIZED = 4401
    FORBIDDEN = 4403
    HELLO_TIMEOUT = 4408
    CONFLICT = 4409
    LIMITED = 4429


def close_code_for(status: int) -> int:
    """The application close code of an HTTP refusal: 401 → 4401, 403 → 4403."""
    return APPLICATION_CODES + status


class SocketRefusedError(Exception):
    """The session ends the socket with a code: a refusal or a limit it reached."""

    def __init__(self, code: int, reason: str = "") -> None:
        super().__init__(reason or str(code))
        self.code = code
        self.reason = reason


@dataclass(frozen=True, slots=True)
class Hello:
    """The first frame: the protocol version, the access token and the route's own fields."""

    version: int
    token: str
    fields: Mapping[str, Any]


# Сокет — участник множества открытых: равенство и хэш — по самому объекту.
@dataclass(slots=True, eq=False)
class GatewaySocket:
    """One accepted socket of a session; `stopping` is set when the process drains."""

    websocket: WebSocket
    route: str
    hello_within: timedelta = HELLO_TIMEOUT
    stopping: asyncio.Event = field(default_factory=asyncio.Event)

    async def hello(self) -> Hello:
        """The `hello` frame; a late or malformed one ends the session with 4408 or 4400."""
        try:
            async with asyncio.timeout(self.hello_within.total_seconds()):
                text = await self.websocket.receive_text()
        except TimeoutError as late:
            raise SocketRefusedError(SocketClose.HELLO_TIMEOUT, "hello_timeout") from late
        except KeyError as binary:
            # Первым пришёл двоичный кадр: у Starlette в нём нет текста.
            raise SocketRefusedError(SocketClose.BAD_HELLO, "bad_hello") from binary
        return parse_hello(text)

    async def send_json(self, frame: Mapping[str, Any]) -> None:
        """A control frame."""
        await self.websocket.send_text(json.dumps(frame, separators=(",", ":")))

    async def send_bytes(self, data: bytes) -> None:
        """A binary frame: audio or another payload of the route."""
        await self.websocket.send_bytes(data)

    async def frames(self) -> AsyncIterator[str | bytes]:
        """The client's frames, text or binary, until it disconnects."""
        while True:
            message = await self.websocket.receive()
            if message["type"] == "websocket.disconnect":
                return
            text, data = message.get("text"), message.get("bytes")
            if data is not None:
                yield data
            elif text is not None:
                yield text

    async def close(self, code: int, reason: str = "") -> None:
        """Close unless the client or the server already did."""
        if self.websocket.application_state is WebSocketState.DISCONNECTED:
            return
        with contextlib.suppress(RuntimeError, WebSocketDisconnect, OSError):
            await self.websocket.close(code=code, reason=reason)


def parse_hello(text: str) -> Hello:
    """`hello` from its frame's text; anything else is a 4400 refusal."""
    try:
        frame = json.loads(text)
    except json.JSONDecodeError as wrong:
        raise SocketRefusedError(SocketClose.BAD_HELLO, "bad_hello") from wrong
    if not isinstance(frame, dict) or frame.get("type") != "hello":
        raise SocketRefusedError(SocketClose.BAD_HELLO, "bad_hello")
    version, token = frame.get("v"), frame.get("token")
    if not isinstance(version, int) or not isinstance(token, str) or not token:
        raise SocketRefusedError(SocketClose.BAD_HELLO, "bad_hello")
    fields = {key: value for key, value in frame.items() if key not in {"type", "v", "token"}}
    return Hello(version, token, fields)


class SocketMetrics:
    """Open sockets, their ends by close code and their lifetimes, by route."""

    def __init__(self, registry: CollectorRegistry) -> None:
        self._open = Gauge(
            "shosai_ws_sockets_open", "WebSockets open now.", ("route",), registry=registry
        )
        self._closed = Counter(
            "shosai_ws_sockets_closed", "WebSockets closed, by close code.",
            ("route", "code"), registry=registry,
        )  # fmt: skip
        self._seconds = Histogram(
            "shosai_ws_socket_seconds", "Lifetime of a WebSocket.", ("route",),
            buckets=SECONDS_BUCKETS, registry=registry,
        )  # fmt: skip

    def opened(self, route: str) -> None:
        """A socket was accepted."""
        self._open.labels(route=route).inc()

    def ended(self, route: str, code: int, seconds: float) -> None:
        """An accepted socket ended."""
        self._open.labels(route=route).dec()
        self._seconds.labels(route=route).observe(seconds)
        self.refused(route, code)

    def refused(self, route: str, code: int) -> None:
        """A socket closed with a code, accepted or not."""
        self._closed.labels(route=route, code=str(code)).inc()


type Session = Callable[[GatewaySocket], Awaitable[None]]


class SocketGateway:
    """The process's sockets: origin, capacity, the session's end, and the drain."""

    def __init__(
        self,
        origins: frozenset[str],
        capacity: int,
        metrics: SocketMetrics,
        hello_within: timedelta = HELLO_TIMEOUT,
    ) -> None:
        self._origins = origins
        self._capacity = capacity
        self._metrics = metrics
        self._hello_within = hello_within
        self._open: set[GatewaySocket] = set()
        self._empty = asyncio.Event()
        self._empty.set()

    @property
    def open_count(self) -> int:
        """Sockets the process holds now."""
        return len(self._open)

    @property
    def capacity(self) -> int:
        """Sockets the process may hold."""
        return self._capacity

    def trusts(self, origin: str | None) -> bool:
        """Whether an upgrade from this origin is the cabinet's."""
        return origin in self._origins

    async def serve(self, websocket: WebSocket, route: str, session: Session) -> None:
        """Run a session on the socket and close it with the code its end deserves."""
        if not self.trusts(websocket.headers.get("origin")):
            await websocket.close(code=SocketClose.FORBIDDEN)
            self._metrics.refused(route, SocketClose.FORBIDDEN)
            log.info("Сокет с чужого origin отклонён", route=route)
            return
        await websocket.accept()
        if len(self._open) >= self._capacity:
            await websocket.close(code=SocketClose.TRY_LATER)
            self._metrics.refused(route, SocketClose.TRY_LATER)
            log.warning("Шлюз полон: сокет закрыт с 1013", route=route, capacity=self._capacity)
            return
        socket = GatewaySocket(websocket, route, self._hello_within)
        self._open.add(socket)
        self._empty.clear()
        self._metrics.opened(route)
        started = time.monotonic()
        code, reason = await self._run(socket, session)
        self._open.discard(socket)
        if not self._open:
            self._empty.set()
        await socket.close(code, reason)
        self._metrics.ended(route, code, time.monotonic() - started)

    async def _run(self, socket: GatewaySocket, session: Session) -> tuple[int, str]:
        try:
            await session(socket)
        except SocketRefusedError as refusal:
            return refusal.code, refusal.reason
        except WebSocketDisconnect as gone:
            return gone.code, ""
        except Exception:
            log.exception("Сессия сокета упала", route=socket.route)
            return SocketClose.INTERNAL, ""
        return (SocketClose.RESTART if socket.stopping.is_set() else SocketClose.NORMAL), ""

    async def drain(self, grace: timedelta) -> None:
        """Tell every socket the process stops, wait for the sessions, close the rest."""
        sockets = list(self._open)
        if not sockets:
            return
        log.info("Шлюз останавливается: сокетам отправлен server.shutdown", sockets=len(sockets))
        for socket in sockets:
            socket.stopping.set()
            with contextlib.suppress(RuntimeError, WebSocketDisconnect, OSError):
                await socket.send_json(SHUTDOWN_FRAME)
        with contextlib.suppress(TimeoutError):
            async with asyncio.timeout(grace.total_seconds()):
                await self._empty.wait()
        for socket in list(self._open):
            await socket.close(SocketClose.RESTART)


def socket_gateway(settings: Settings, registry: CollectorRegistry) -> SocketGateway:
    """The process's gateway: the cabinet's origin of `PUBLIC_BASE_URL` and the CORS allowlist
    (the development cabinet), the capacity of `WS_SOCKETS_PER_PROCESS`."""
    cabinet = normalize_origin(str(settings.email.public_base_url))
    origins = frozenset((cabinet, *settings.web.cors_allowed_origins))
    return SocketGateway(origins, settings.server.ws_sockets_per_process, SocketMetrics(registry))
