"""Doubles of the voice relay's ends for its tests: the cabinet, Gemini, the agent, the minutes."""

import asyncio
import json
import time
import uuid
from collections.abc import AsyncIterator, Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Final

from shosai.core.ai.requests import ToolSchema
from shosai.core.ai.results import LiveEnd, LiveEvent, LiveToolCall
from shosai.features.agent.contracts.voice import VoiceEvents, VoiceExchange

CARD: Final = uuid.uuid4()
FOUND: Final = json.dumps({"result": "Budget review: travel cut by 20%"})


@dataclass
class Cabinet:
    """The cabinet's socket: the frames a test sends, and what the relay sent back."""

    stopping: asyncio.Event = field(default_factory=asyncio.Event)
    inbox: asyncio.Queue[str | bytes | None] = field(default_factory=asyncio.Queue)
    sent: list[dict[str, Any]] = field(default_factory=list)
    audio: list[bytes] = field(default_factory=list)

    async def send_json(self, frame: Mapping[str, Any]) -> None:
        """A control frame of the relay."""
        self.sent.append(dict(frame))

    async def send_bytes(self, data: bytes) -> None:
        """Leo's speech."""
        self.audio.append(data)

    async def frames(self) -> AsyncIterator[str | bytes]:
        """What the test puts, until it puts None (the cabinet left)."""
        while (frame := await self.inbox.get()) is not None:
            yield frame

    def kinds(self) -> list[str]:
        """The sent frames, each as its type and its one telling field."""
        return [
            f"{f['type']}:{f.get('state') or f.get('who') or f.get('status') or ''}"
            for f in self.sent
        ]


@dataclass
class Gemini:
    """Gemini's side: the events a test puts, and the audio and results the relay sent."""

    queue: asyncio.Queue[LiveEvent] = field(default_factory=asyncio.Queue)
    audio: list[bytes] = field(default_factory=list)
    results: list[tuple[str, str]] = field(default_factory=list)

    async def send_audio(self, pcm: bytes) -> None:
        """The person's speech."""
        self.audio.append(pcm)

    async def send_tool_result(self, call: LiveToolCall, result: str) -> None:
        """A tool's answer."""
        self.results.append((call.call_id, result))

    async def events(self) -> AsyncIterator[LiveEvent]:
        """The events put, through `LiveEnd`."""
        while True:
            event = await self.queue.get()
            yield event
            if isinstance(event, LiveEnd):
                return

    async def put(self, *events: LiveEvent) -> None:
        """Events Gemini sends, in order."""
        for event in events:
            await self.queue.put(event)


@dataclass
class Talk:
    """The agent's conversation: a call steps, may wait at its gate, may fail, may propose."""

    thread_id: uuid.UUID = field(default_factory=uuid.uuid4)
    cross_border_consent: bool = False
    instruction: str = "Speak briefly."
    tools: tuple[ToolSchema, ...] = ()
    gate: asyncio.Event = field(default_factory=asyncio.Event)
    fail: bool = False
    calls: list[str] = field(default_factory=list)
    # Фраза человека, с которой пришёл каждый вызов.
    heard: list[str] = field(default_factory=list)
    exchanges: list[VoiceExchange] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.gate.set()

    async def call(self, call: tuple[str, str, str], events: VoiceEvents, *, heard: str) -> str:
        """A step, the gate, then the result or a card."""
        _, name, _ = call
        self.calls.append(name)
        self.heard.append(heard)
        await events.step(name, "running")
        await self.gate.wait()
        if self.fail:
            message = "сбой инструмента в тесте"
            raise RuntimeError(message)
        await events.step(name, "done")
        if name == "tasks__create":
            await events.proposed(CARD)
        return FOUND

    async def record(self, exchange: VoiceExchange) -> None:
        """Keep the exchange."""
        self.exchanges.append(exchange)


@dataclass
class Minutes:
    """The month's minutes: how many minutes may still be counted."""

    left: int = 30
    counted: int = 0

    async def minute(self) -> bool:
        """Count a minute."""
        self.counted += 1
        return self.counted < self.left


async def until(check: Callable[[], object], seconds: float = 3.0) -> None:
    """Wait until the check holds."""
    deadline = time.monotonic() + seconds
    while not check():
        if time.monotonic() > deadline:
            message = "условие теста не наступило"
            raise TimeoutError(message)
        await asyncio.sleep(0.005)
