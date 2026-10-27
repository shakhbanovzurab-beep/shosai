"""What the voice relay uses of its two ends and of the minutes, and its times (ADR 0070).

The gateway's socket, the AI port's live session and the conversation's meter fit these
shapes as they are; the relay's tests give it doubles of the same shapes.
"""

import asyncio
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Final, Protocol

from starlette.websockets import WebSocketDisconnect

from shosai.core.ai.results import LiveEvent, LiveToolCall
from shosai.features.capture.domain.voice import IDLE, LONGEST

# Кабинет ушёл: отправка в закрытый сокет — не ошибка разговора.
GONE: Final = (RuntimeError, WebSocketDisconnect, OSError)


class CabinetSocket(Protocol):
    """The cabinet's side: control frames, speech, the person's frames and the drain."""

    stopping: asyncio.Event

    async def send_json(self, frame: Mapping[str, Any]) -> None:
        """A control frame."""
        ...

    async def send_bytes(self, data: bytes) -> None:
        """Leo's speech."""
        ...

    def frames(self) -> AsyncIterator[str | bytes]:
        """The cabinet's frames until it goes."""
        ...


class LiveVoice(Protocol):
    """Gemini's side: the person's speech in, tool results back, events out."""

    async def send_audio(self, pcm: bytes) -> None:
        """A piece of the person's speech."""
        ...

    async def send_tool_result(self, call: LiveToolCall, result: str) -> None:
        """A tool's answer."""
        ...

    def events(self) -> AsyncIterator[LiveEvent]:
        """What Gemini says and asks, ending with `LiveEnd`."""
        ...


class MinuteMeter(Protocol):
    """The conversation's minutes."""

    async def minute(self) -> bool:
        """Count another minute; False when the month's minutes are used up."""
        ...


@dataclass(frozen=True, slots=True)
class RelayTimes:
    """The conversation's limits and how often the watch looks at them."""

    longest: timedelta = LONGEST
    idle: timedelta = IDLE
    minute: timedelta = timedelta(minutes=1)
    check_every: timedelta = timedelta(seconds=5)


DEFAULT_TIMES: Final = RelayTimes()
