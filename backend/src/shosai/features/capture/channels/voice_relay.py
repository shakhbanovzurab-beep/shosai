"""One voice conversation between the cabinet's socket and a Gemini Live session (LV-D2, LV-D5).

Four loops run together and the first to finish ends the conversation: the cabinet's frames
(speech to Gemini, `end` from the person), Gemini's events (speech and words to the cabinet,
tool calls to the agent, an exchange recorded when Leo's turn ends or the person interrupts
it), the watch (30 minutes at most, two without speech, the minutes every minute) and the
process's drain. A tool call runs beside them, so speech keeps flowing; one Gemini cancels
is cancelled. Whatever was said when the conversation ends is recorded as interrupted.
"""

import asyncio
import json
import time
from collections.abc import Callable, Coroutine
from contextlib import suppress
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog

from shosai.core.ai.errors import AiCallError
from shosai.core.ai.results import (
    LiveAudio,
    LiveChannel,
    LiveEnd,
    LiveInterrupted,
    LiveText,
    LiveToolCall,
    LiveToolsCancelled,
    LiveTurnEnd,
)
from shosai.features.agent.contracts.voice import VoiceConversation, VoiceExchange
from shosai.features.capture.channels.voice_links import (
    DEFAULT_TIMES,
    GONE,
    CabinetSocket,
    LiveVoice,
    MinuteMeter,
    RelayTimes,
)
from shosai.features.capture.domain import voice as wire
from shosai.features.capture.domain.exchanges import Exchange
from shosai.features.capture.domain.voice import VoiceEnd, VoiceState
from shosai.features.capture.infrastructure.voice_texts import TOOL_FAILED

type TurnEvent = LiveToolCall | LiveToolsCancelled | LiveInterrupted | LiveTurnEnd
log = structlog.stdlib.get_logger(__name__)


class SocketEvents:
    """A tool call's steps and cards, told to the cabinet."""

    def __init__(self, relay: VoiceRelay) -> None:
        self._relay = relay

    async def step(self, activity: str, status: str) -> None:
        """A step of the call."""
        await self._relay.send(wire.step(activity, status))

    async def proposed(self, action_id: UUID) -> None:
        """A write became a card."""
        await self._relay.send(wire.proposed(action_id))


class VoiceRelay:
    """Relays one conversation until it ends; returns why it ended."""

    def __init__(
        self,
        ends: tuple[CabinetSocket, LiveVoice],
        talk: tuple[VoiceConversation, MinuteMeter],
        times: RelayTimes = DEFAULT_TIMES,
        clocks: tuple[Callable[[], datetime], Callable[[], float]] = (
            lambda: datetime.now(UTC), time.monotonic,
        ),
    ) -> None:  # fmt: skip
        self._socket, self._live = ends
        self._talk, self._meter = talk
        self._times = times
        self._clock, self._monotonic = clocks
        self._exchange = Exchange()
        self._shown: VoiceState | None = None
        self._calls: dict[str, asyncio.Task[None]] = {}
        self._events = SocketEvents(self)
        self._voice_at = self._monotonic()

    async def run(self) -> VoiceEnd:
        """Relay until the person ends it, a limit is reached, Gemini fails or the process stops."""
        await self._show(VoiceState.LISTENING)
        loops = [
            spawn(self._from_cabinet()), spawn(self._from_model()), spawn(self._watch()),
            spawn(self._stopping()),
        ]  # fmt: skip
        try:
            done, _ = await asyncio.wait(loops, return_when=asyncio.FIRST_COMPLETED)
        finally:
            running = [*loops, *self._calls.values()]
            for task in running:
                task.cancel()
            await asyncio.gather(*running, return_exceptions=True)
        end = first_end(done)
        await self._close_exchange(interrupted=True)
        return end

    async def send(self, frame: wire.Frame) -> None:
        """A control frame, unless the cabinet is gone."""
        with suppress(*GONE):
            await self._socket.send_json(frame)

    async def _from_cabinet(self) -> VoiceEnd:
        try:
            async for frame in self._socket.frames():
                if isinstance(frame, bytes):
                    if frame and len(frame) % 2 == 0:
                        await self._live.send_audio(frame)
                elif is_end(frame):
                    return VoiceEnd.ENDED
        except AiCallError as broken:
            log.warning("Звук не ушёл в Gemini Live", failure=broken.code)
            return VoiceEnd.PROVIDER
        return VoiceEnd.ENDED

    async def _from_model(self) -> VoiceEnd:
        async for event in self._live.events():
            match event:
                case LiveEnd(failure=failure):
                    return VoiceEnd.PROVIDER if failure is not None else VoiceEnd.ENDED
                case LiveAudio() | LiveText():
                    await self._on_speech(event)
                case _:
                    await self._on_turn(event)
        return VoiceEnd.ENDED

    async def _on_speech(self, event: LiveAudio | LiveText) -> None:
        match event:
            case LiveAudio(data=data):
                self._voice_at = self._monotonic()
                await self._show(VoiceState.SPEAKING)
                with suppress(*GONE):
                    await self._socket.send_bytes(data)
            case LiveText(channel=LiveChannel.INPUT):
                self._voice_at = self._monotonic()
                phrase = self._exchange.hear(event.text, self._clock(), final=event.final)
                await self.send(wire.transcript("person", phrase.text, final=phrase.finished))
            case LiveText():
                words = self._exchange.say(event.text, self._clock())
                await self.send(wire.transcript("leo", words, final=event.final))

    async def _on_turn(self, event: TurnEvent) -> None:
        match event:
            case LiveToolCall():
                await self._show(VoiceState.THINKING)
                self._call(event)
            case LiveToolsCancelled(call_ids=cancelled):
                for call_id in cancelled:
                    if (task := self._calls.pop(call_id, None)) is not None:
                        task.cancel()
            case LiveInterrupted():
                await self.send(wire.INTERRUPTED)
                await self._close_exchange(interrupted=True)
                await self._show(VoiceState.LISTENING)
            case LiveTurnEnd():
                if self._exchange.answered:
                    await self._close_exchange(interrupted=False)
                # Конец хода сразу после вызова: Leo ещё ждёт инструмент и заговорит после него.
                if not self._calls:
                    await self._show(VoiceState.LISTENING)

    def _call(self, call: LiveToolCall) -> None:
        self._exchange.call(self._clock())
        task = spawn(self._answer(call))
        self._calls[call.call_id] = task
        task.add_done_callback(lambda _: self._calls.pop(call.call_id, None))

    async def _answer(self, call: LiveToolCall) -> None:
        try:
            result = await self._talk.call(call.call_id, call.name, call.arguments, self._events)
        except Exception:
            log.exception("Инструмент голосового разговора не ответил", tool=call.name)
            result = TOOL_FAILED
        try:
            await self._live.send_tool_result(call, result)
        except AiCallError as broken:
            log.warning("Ответ инструмента не ушёл в Gemini Live", failure=broken.code)

    async def _close_exchange(self, *, interrupted: bool) -> None:
        exchange, at = self._exchange, self._clock()
        self._exchange = exchange.following(at)
        if exchange.empty or exchange.started_at is None:
            return
        said = VoiceExchange(
            exchange.question, exchange.answer, exchange.started_at, at, interrupted
        )
        try:
            await self._talk.record(said)
        except Exception:
            log.exception(
                "Обмен голосового разговора не записан", thread_id=str(self._talk.thread_id)
            )

    async def _watch(self) -> VoiceEnd:
        started = minute_at = self._monotonic()
        times = self._times
        while True:
            await asyncio.sleep(times.check_every.total_seconds())
            now = self._monotonic()
            if now - started >= times.longest.total_seconds():
                return VoiceEnd.TIME_LIMIT
            if now - self._voice_at >= times.idle.total_seconds():
                return VoiceEnd.IDLE
            if now - minute_at >= times.minute.total_seconds():
                minute_at = now
                if not await self._meter.minute():
                    return VoiceEnd.MINUTES

    async def _stopping(self) -> VoiceEnd:
        await self._socket.stopping.wait()
        return VoiceEnd.SHUTDOWN

    async def _show(self, current: VoiceState) -> None:
        if current is not self._shown:
            self._shown = current
            await self.send(wire.state(current))


def spawn[T](work: Coroutine[Any, Any, T]) -> asyncio.Task[T]:
    """A loop or a call of the conversation."""
    return asyncio.create_task(work, name="capture.voice")


def first_end(done: set[asyncio.Task[VoiceEnd]]) -> VoiceEnd:
    """The end of a loop that finished; when each one failed, their failures together."""
    failures = [failure for task in done if (failure := task.exception()) is not None]
    if len(failures) < len(done):
        return next(task.result() for task in done if task.exception() is None)
    message = "циклы голосового разговора упали"
    raise BaseExceptionGroup(message, failures)


def is_end(text: str) -> bool:
    """Whether a control frame of the cabinet is `end`; anything else is skipped."""
    try:
        frame = json.loads(text)
    except json.JSONDecodeError:
        return False
    return isinstance(frame, dict) and frame.get("type") == "end"
