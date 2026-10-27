"""`WS /v1/ws/voice`: a person's conversation with Leo, from `hello` to its end (ADR 0070).

After `hello` — protocol 1, the access token and the place — identity names the person. A
second conversation of theirs is refused (4409) while the first holds its lock, and so is
one with the month's minutes used up (4402); the agent then opens the conversation on its
thread, and its refusals end the socket with `4000 + status`. Gemini Live opens with Leo's
instruction, the voice Charon and the page's tools — a refusal of the AI port ends with its
status, 4503 when Gemini is down. `ready` follows and the relay runs until the end, which
`ended` names: the minutes used up close with 4402, Gemini lost with 4503, the rest
normally (1012 while the process stops). The seconds are written however it ended.
"""

import time
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Final

import structlog

from shosai.core.ai.calls import CallClass, CallContext, CallOrigin, ModelRef
from shosai.core.ai.errors import AiCallError
from shosai.core.ai.port import AiProviders
from shosai.core.ai.requests import VoiceSetup
from shosai.core.ai.sessions.live import LiveSession
from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.errors import AppError
from shosai.core.kv.locks import DistributedLocks, LockLease, LockOutagePolicy, LockUnavailableError
from shosai.core.ports.directory import PortDirectory
from shosai.core.web.sockets import GatewaySocket, SocketClose, SocketRefusedError, close_code_for
from shosai.features.agent.contracts.voice import VOICE_TURNS, VoiceConversation, VoiceStart
from shosai.features.capture.application.voice_minutes import LOCK_TTL, VoiceMeter, minutes_left
from shosai.features.capture.channels.voice_links import DEFAULT_TIMES, GONE, RelayTimes
from shosai.features.capture.channels.voice_relay import VoiceRelay
from shosai.features.capture.domain import voice as wire
from shosai.features.capture.domain.voice import (
    PROTOCOL,
    SILENCE_MS,
    VOICE,
    MalformedHelloError,
    VoiceEnd,
    VoicePlace,
    voice_place,
)
from shosai.features.capture.infrastructure.voice_metrics import VoiceMetrics
from shosai.features.identity.contracts import Principal
from shosai.features.identity.contracts.sockets import socket_principal

ROUTE: Final = "/v1/ws/voice"
# Концы разговора, которые закрывают сокет кодом отказа: кабинет показывает причину.
REFUSING_ENDS: Final = {
    VoiceEnd.MINUTES: close_code_for(HTTPStatus.PAYMENT_REQUIRED),
    VoiceEnd.PROVIDER: close_code_for(HTTPStatus.SERVICE_UNAVAILABLE),
}
log = structlog.stdlib.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class VoiceParts:
    """What voice conversations work with."""

    transactions: HomeTransactions
    ports: PortDirectory
    locks: DistributedLocks
    ai: AiProviders
    model: ModelRef
    metrics: VoiceMetrics


class VoiceSessions:
    """Serves the gateway's voice sockets."""

    def __init__(
        self,
        parts: VoiceParts,
        times: RelayTimes = DEFAULT_TIMES,
        clocks: tuple[Callable[[], datetime], Callable[[], float]] = (
            lambda: datetime.now(UTC), time.monotonic,
        ),
    ) -> None:  # fmt: skip
        self._parts = parts
        self._times = times
        self._clocks = clocks

    async def serve(self, socket: GatewaySocket) -> None:
        """One conversation on the socket; a refusal or an end that refuses raises its code."""
        hello = await socket.hello()
        try:
            if hello.version != PROTOCOL:
                raise MalformedHelloError
            place = voice_place(hello.fields)
        except MalformedHelloError as wrong:
            raise SocketRefusedError(SocketClose.BAD_HELLO, "bad_hello") from wrong
        person = await socket_principal(self._parts.ports, hello)
        lock = f"capture.voice.{person.user_id}"
        try:
            async with self._parts.locks.hold(
                lock, ttl=LOCK_TTL, outage=LockOutagePolicy.FAIL_CLOSED
            ) as lease:
                if lease is None:
                    raise SocketRefusedError(SocketClose.CONFLICT, "voice_busy")
                end = await self._converse(socket, person, place, lease)
        except LockUnavailableError as down:
            raise SocketRefusedError(
                REFUSING_ENDS[VoiceEnd.PROVIDER], "voice_unavailable"
            ) from down
        if end in REFUSING_ENDS:
            raise SocketRefusedError(REFUSING_ENDS[end], end.value)

    async def _converse(
        self, socket: GatewaySocket, person: Principal, place: VoicePlace, lease: LockLease
    ) -> VoiceEnd:
        parts = self._parts
        start = VoiceStart(place.workspace_id, place.thread_id, place.path, place.locale)
        try:
            await minutes_left(parts.transactions, parts.ports, person)
            talk = await parts.ports.get(VOICE_TURNS).open(person, start)
        except AppError as refused:
            raise SocketRefusedError(close_code_for(refused.status), refused.code) from refused
        meter = VoiceMeter((parts.transactions, parts.ports, lease), person, self._clocks[0])
        context = CallContext(
            effect_key=f"capture.voice:{meter.id}", feature="capture.voice",
            call_class=CallClass.EXPENSIVE, origin=CallOrigin.INTERACTIVE, scope=person.scope(),
            cross_border_consent=talk.cross_border_consent,
        )  # fmt: skip
        setup = VoiceSetup(talk.instruction, VOICE, talk.tools, SILENCE_MS)
        try:
            async with parts.ai.open_voice_session(context, parts.model, setup) as live:
                return await self._relayed(socket, live, (talk, meter))
        except AiCallError as failed:
            log.warning("Gemini Live не открыл голосовой разговор", failure=failed.code)
            raise SocketRefusedError(close_code_for(failed.status), failed.code) from failed

    async def _relayed(
        self,
        socket: GatewaySocket,
        live: LiveSession,
        talk: tuple[VoiceConversation, VoiceMeter],
    ) -> VoiceEnd:
        conversation, meter = talk
        await meter.open()
        log.info("Голосовой разговор открыт", session_id=str(meter.id))
        # Упавший релей записывается как обрыв Gemini: секунды при этом не теряются.
        end = VoiceEnd.PROVIDER
        try:
            with suppress(*GONE):
                await socket.send_json(
                    wire.ready(meter.id, conversation.thread_id, live.input_rate)
                )
            end = await VoiceRelay((socket, live), talk, self._times, self._clocks).run()
        finally:
            await meter.finish(end)
            self._parts.metrics.ended(end, meter.seconds())
            log.info("Голосовой разговор закончен", session_id=str(meter.id), end=end.value)
        with suppress(*GONE):
            await socket.send_json(wire.ended(end))
        return end
