"""Scenarios of the local live server: OpenAI Realtime and Gemini Live as the tests need them."""

import asyncio
import base64
import json
from collections.abc import Callable
from dataclasses import dataclass, field

from websockets.asyncio.server import ServerConnection
from websockets.exceptions import ConnectionClosed

from shosai.core.ai.results import LiveEvent
from shosai.core.ai.sessions.live import LiveSession
from tests.doubles.live_server import Json, LiveServer, Scenario

SPOKEN = base64.b64encode(b"\x01\x00" * 8).decode("ascii")


async def send(connection: ServerConnection, message: Json) -> None:
    """Send one JSON message."""
    await connection.send(json.dumps(message))


def openai_scenario(
    *, seconds: float | None = 60.0, drop_after: int | None = None, refuse_setup: bool = False
) -> Scenario:
    """A transcription session: each committed turn is transcribed with `seconds` of usage."""

    async def run(connection: ServerConnection, server: LiveServer) -> None:
        await server.receive(connection)
        if refuse_setup:
            await send(connection, {"type": "error", "error": {"code": "invalid_value"}})
            return
        await send(connection, {"type": "session.updated", "session": {}})
        turns = 0
        try:
            while True:
                message = await server.receive(connection)
                if message.get("type") != "input_audio_buffer.commit":
                    continue
                turns += 1
                item = {"item_id": f"item_{turns}"}
                await send(connection, {"type": "conversation.item.input_audio_transcription.delta",
                                        "delta": "Hel", **item})  # fmt: skip
                done: Json = {"type": "conversation.item.input_audio_transcription.completed",
                              "transcript": f"Hello {turns}.", **item}  # fmt: skip
                if seconds is not None:
                    done["usage"] = {"type": "duration", "seconds": seconds}
                await send(connection, done)
                if turns == drop_after:
                    await connection.close(code=1011, reason="server error")
                    return
        except ConnectionClosed:
            return

    return run


def gemini_scenario(
    *, tool_call: bool = False, drop: bool = False, interrupted: bool = False
) -> Scenario:
    """A Live session: every audio piece is answered with texts, speech and usage; with
    `interrupted`, the person speaks over the model and it drops its pending tool call."""

    async def run(connection: ServerConnection, server: LiveServer) -> None:
        await server.receive(connection)
        await send(connection, {"setupComplete": {}})
        try:
            while True:
                message = await server.receive(connection)
                # Gemini принимает ключи и в camelCase, и в snake_case; SDK шлёт snake_case.
                streamed = message.get("realtimeInput") or message.get("realtime_input") or {}
                if "audio" not in streamed:
                    continue
                if interrupted:
                    await interruption(connection)
                    continue
                await answer(connection, tool_call=tool_call)
                if drop:
                    await connection.close(code=1011, reason="internal error")
                    return
        except ConnectionClosed:
            return

    return run


async def answer(connection: ServerConnection, *, tool_call: bool) -> None:
    """One turn of the model: both transcripts, speech, a tool call if asked, then usage."""
    for side, text in (("inputTranscription", "Привет"), ("outputTranscription", "Hello")):
        await send(connection, {"serverContent": {side: {"text": text, "finished": True}}})
    await send(connection, {"serverContent": {"modelTurn": {"parts": [
        {"inlineData": {"mimeType": "audio/pcm;rate=24000", "data": SPOKEN}}]}}})  # fmt: skip
    if tool_call:
        await send(connection, {"toolCall": {"functionCalls": [
            {"id": "call-1", "name": "consult", "args": {"question": "When?"}}]}})  # fmt: skip
    await send(connection, {
        "serverContent": {"turnComplete": True},
        "usageMetadata": {
            "promptTokensDetails": [{"modality": "AUDIO", "tokenCount": 50},
                                    {"modality": "TEXT", "tokenCount": 25}],
            "responseTokensDetails": [{"modality": "AUDIO", "tokenCount": 50},
                                      {"modality": "TEXT", "tokenCount": 10}],
        },
    })  # fmt: skip


async def interruption(connection: ServerConnection) -> None:
    """The model starts speaking and calling a tool, the person speaks over it."""
    await send(connection, {"serverContent": {"modelTurn": {"parts": [
        {"inlineData": {"mimeType": "audio/pcm;rate=24000", "data": SPOKEN}}]}}})  # fmt: skip
    await send(connection, {"toolCall": {"functionCalls": [
        {"id": "call-1", "name": "consult", "args": {}}]}})  # fmt: skip
    await send(connection, {"serverContent": {"interrupted": True}})
    await send(connection, {"toolCallCancellation": {"ids": ["call-1"]}})
    await send(connection, {"serverContent": {"turnComplete": True}})


@dataclass
class Reader:
    """Reads a session's events in the background; a test waits for what it expects."""

    events: list[LiveEvent] = field(default_factory=list)
    seen: asyncio.Condition = field(default_factory=asyncio.Condition)
    task: asyncio.Task[None] | None = None

    def start(self, session: LiveSession) -> Reader:
        """Begin reading."""
        self.task = asyncio.create_task(self._read(session))
        return self

    async def until(self, enough: Callable[[list[LiveEvent]], bool]) -> None:
        """Wait, 5 s at most, until the events read satisfy the condition."""
        async with asyncio.timeout(5), self.seen:
            await self.seen.wait_for(lambda: enough(self.events))

    async def finished(self) -> list[LiveEvent]:
        """Every event, once the session has ended."""
        assert self.task is not None
        async with asyncio.timeout(5):
            await self.task
        return self.events

    async def _read(self, session: LiveSession) -> None:
        async for event in session.events():
            async with self.seen:
                self.events.append(event)
                self.seen.notify_all()
