"""Calling an app the way a server does, with a scope built from the request line."""

from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from starlette.types import ASGIApp, Message

type Receive = Callable[[], Awaitable[Message]]
type Send = Callable[[Message], Awaitable[None]]


def asgi_scope(
    method: str, path: str, *, query: str = "", headers: Sequence[tuple[bytes, bytes]] = ()
) -> dict[str, Any]:
    """An HTTP scope as uvicorn builds it; any method and path a client can send."""
    return {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": method,
        "scheme": "http", "path": path, "raw_path": path.encode(), "root_path": "",
        "query_string": query.encode(), "headers": [(b"host", b"t"), *headers],
        "client": ("127.0.0.1", 1), "server": ("t", 80),
    }  # fmt: skip


async def empty_body() -> Message:
    """A request without a body."""
    return {"type": "http.request", "body": b"", "more_body": False}


async def discard(_message: Message) -> None:
    """The response goes nowhere."""


async def call(
    app: ASGIApp,
    scope: dict[str, Any],
    *,
    receive: Receive = empty_body,
    send: Send = discard,
) -> None:
    """One request through the app."""
    await app(scope, receive, send)
