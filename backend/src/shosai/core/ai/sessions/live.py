"""Live sessions with a provider: audio in, text, speech and tool calls out (F6 step 3b).

An adapter opens a `LiveConnection`; the port wraps it in a `LiveSession` that meters it.
Usage the provider reports goes to the session's minute meter and never reaches the caller.
When the session ends, the audio sent sets a floor: a provider that reported less than the
audio it was given — a lost usage message, a broken socket — is billed at least that much,
so a session never costs nothing (the draft's wall-clock backstop).

Opening waits at most 3 s and is tried once more on a transient failure (§4.3); a session
that breaks later ends with `LiveEnd` and a closed code, and the caller decides whether to
open another.
"""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Final, Protocol

import structlog

from shosai.core.ai.errors import AiCallError, AiFailure
from shosai.core.ai.recording import MeteredCall
from shosai.core.ai.results import LiveEnd, LiveEvent, LiveToolCall, LiveUsage, Usage
from shosai.core.ai.sessions.minutes import MinuteRows, SessionMeter, merged

CONNECT_TIMEOUT: Final = 3.0
TRANSIENT: Final = frozenset({AiFailure.PROVIDER_ERROR, AiFailure.DEADLINE_EXCEEDED})
PCM_SAMPLE_BYTES: Final = 2
log = structlog.stdlib.get_logger(__name__)


class LiveConnection(Protocol):
    """An open session with a provider, as an adapter hands it to the port."""

    @property
    def input_rate(self) -> int:
        """The sample rate of the PCM16 mono audio the session takes."""
        ...

    async def send_audio(self, pcm: bytes) -> None:
        """Send a piece of audio."""
        ...

    async def end_turn(self) -> None:
        """Tell the provider the speaker stopped, without waiting for its silence detector."""
        ...

    async def send_tool_result(self, call: LiveToolCall, result: str) -> None:
        """Answer a tool call with its JSON result."""
        ...

    def events(self) -> AsyncIterator[LiveEvent | LiveUsage]:
        """What the provider sends, ending with `LiveEnd`."""
        ...

    def floor(self, seconds: float) -> Usage:
        """The least usage `seconds` of input audio is billed at."""
        ...

    async def close(self) -> None:
        """Close the session; its events then end with `LiveEnd(None)`."""
        ...


def shortfall(reported: Usage, floor: Usage) -> Usage | None:
    """What the reported usage lacks to reach the floor, in the floor's own measures."""
    seconds = floor.units - reported.units if floor.unit is not None else Decimal(0)
    audio_tokens = floor.input_audio_tokens - reported.input_audio_tokens
    if seconds <= 0 and audio_tokens <= 0:
        return None
    return Usage(
        input_audio_tokens=max(audio_tokens, 0),
        units=max(seconds, Decimal(0)),
        unit=floor.unit if seconds > 0 else None,
    )


class LiveSession:
    """A caller's live session: send audio, read events; metered minute by minute."""

    def __init__(self, connection: LiveConnection, meter: SessionMeter) -> None:
        self._connection = connection
        self._meter = meter
        self._reported = Usage()
        self._sent_bytes = 0

    @property
    def input_rate(self) -> int:
        """The sample rate of the PCM16 mono audio the session takes."""
        return self._connection.input_rate

    async def send_audio(self, pcm: bytes) -> None:
        """Send whole PCM16 samples at the session's input rate."""
        if len(pcm) % PCM_SAMPLE_BYTES:
            message = "звук сессии — целые отсчёты PCM16"
            raise ValueError(message)
        await self._connection.send_audio(pcm)
        self._sent_bytes += len(pcm)

    async def end_turn(self) -> None:
        """Close the speaker's turn now."""
        await self._connection.end_turn()

    async def send_tool_result(self, call: LiveToolCall, result: str) -> None:
        """Answer the model's tool call."""
        await self._connection.send_tool_result(call, result)

    async def events(self) -> AsyncIterator[LiveEvent]:
        """Text, speech and tool calls as they come, ending with `LiveEnd`."""
        async for event in self._connection.events():
            if isinstance(event, LiveUsage):
                self._reported = merged(self._reported, event.usage)
                self._meter.add(event.usage)
                continue
            yield event
            if isinstance(event, LiveEnd):
                return

    def settle(self) -> None:
        """Bill the audio the provider did not report, at the floor of its model."""
        seconds = self._sent_bytes / (self.input_rate * PCM_SAMPLE_BYTES)
        missing = shortfall(self._reported, self._connection.floor(seconds))
        if missing is not None:
            log.warning("Провайдер сообщил меньше расхода, чем ушло звука", seconds=seconds)
            self._meter.add(missing)


class LiveSessions:
    """Opens live sessions within their deadline and meters them until they close."""

    def __init__(self, minutes: MinuteRows, connect_timeout: float = CONNECT_TIMEOUT) -> None:
        self._minutes = minutes
        self._connect_timeout = connect_timeout

    @asynccontextmanager
    async def run(
        self, call: MeteredCall, connect: Callable[[], Awaitable[LiveConnection]]
    ) -> AsyncIterator[LiveSession]:
        """A metered session; its minutes are written when it closes, however it ends."""
        connection = await self._connected(connect)
        meter = self._minutes.open(call)
        session = LiveSession(connection, meter)
        try:
            yield session
        finally:
            session.settle()
            await connection.close()
            await self._minutes.close(meter)

    async def _connected(self, connect: Callable[[], Awaitable[LiveConnection]]) -> LiveConnection:
        try:
            return await self._attempt(connect)
        except AiCallError as error:
            if error.failure not in TRANSIENT:
                raise
            log.warning("Живая сессия не открылась, пробуем ещё раз", failure=error.failure.value)
        return await self._attempt(connect)

    async def _attempt(self, connect: Callable[[], Awaitable[LiveConnection]]) -> LiveConnection:
        try:
            async with asyncio.timeout(self._connect_timeout):
                return await connect()
        except TimeoutError:
            raise AiCallError(AiFailure.DEADLINE_EXCEEDED) from None
