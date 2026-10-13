"""OpenAI Realtime transcription: a meeting's speech streamed to text (ADR 0043).

Facts from OpenAI's documentation (realtime transcription guide and server events, read on
2026-10-13), and the draft's measurements:

- `wss://api.openai.com/v1/realtime?intent=transcription`; from a server the key goes in
  the `Authorization` header — no client secret, which cost the draft 450 ms per session
- `session.update` with `type: transcription` sets the model, PCM16 at 24 kHz (lower rates
  are refused) and server-side turn detection; `session.updated` confirms it
- audio goes as `input_audio_buffer.append` (base64), a turn may be closed early with
  `input_audio_buffer.commit`
- text comes as `...input_audio_transcription.delta` and `.completed` per item, with
  `usage` of type `duration` (seconds) or `tokens`; items may complete out of order and are
  matched by `item_id`; `gpt-live-transcribe` takes `languages`, other models `language`
"""

import base64
import json
import ssl
from collections.abc import AsyncIterator, Mapping
from decimal import Decimal
from typing import Any, Final

import structlog
from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed, InvalidStatus, WebSocketException

from shosai.core.ai.adapters.http_calls import failure_of
from shosai.core.ai.calls import ModelRef
from shosai.core.ai.errors import AiCallError, AiFailure
from shosai.core.ai.requests import LiveTranscriptionSetup
from shosai.core.ai.results import (
    LiveChannel,
    LiveEnd,
    LiveEvent,
    LiveText,
    LiveToolCall,
    LiveUsage,
    Unit,
    Usage,
)

OPENAI_REALTIME: Final = "wss://api.openai.com/v1/realtime?intent=transcription"
INPUT_RATE: Final = 24_000
MAX_MESSAGE_BYTES: Final = 4 * 1024 * 1024
MULTI_LANGUAGE_MODELS: Final = frozenset({"gpt-live-transcribe"})
log = structlog.stdlib.get_logger(__name__)


def session_update(model: str, setup: LiveTranscriptionSetup) -> dict[str, Any]:
    """The `session.update` of a transcription session."""
    transcription: dict[str, Any] = {"model": model}
    if setup.languages and model in MULTI_LANGUAGE_MODELS:
        transcription["languages"] = list(setup.languages)
    elif len(setup.languages) == 1:
        transcription["language"] = setup.languages[0]
    return {
        "type": "session.update",
        "session": {
            "type": "transcription",
            "audio": {
                "input": {
                    "format": {"type": "audio/pcm", "rate": INPUT_RATE},
                    "transcription": transcription,
                    "turn_detection": {
                        "type": "server_vad",
                        "silence_duration_ms": setup.silence_ms,
                    },
                }
            },
        },
    }


def realtime_usage(raw: object) -> Usage | None:
    """Usage of a completed item: seconds of audio, or audio and text tokens."""
    if not isinstance(raw, dict):
        return None
    if raw.get("type") == "duration":
        seconds = raw.get("seconds")
        if not isinstance(seconds, int | float):
            return None
        return Usage(units=Decimal(str(seconds)), unit=Unit.AUDIO_SECOND)
    details = raw.get("input_token_details")
    if not isinstance(details, dict):
        # Без разбивки весь вход считаем звуком: так тарифицирует OpenAI расшифровку.
        details = {"audio_tokens": raw.get("input_tokens")}
    return Usage(
        input_tokens=int(details.get("text_tokens") or 0),
        input_audio_tokens=int(details.get("audio_tokens") or 0),
        output_tokens=int(raw.get("output_tokens") or 0),
    )


def event_of(event: Mapping[str, Any]) -> list[LiveEvent | LiveUsage]:
    """What one server event means for the session."""
    kind = event.get("type")
    item_id = event.get("item_id") if isinstance(event.get("item_id"), str) else None
    if kind == "conversation.item.input_audio_transcription.delta":
        delta = event.get("delta")
        return [LiveText(delta, LiveChannel.INPUT, final=False, item_id=item_id)] if delta else []
    if kind == "conversation.item.input_audio_transcription.completed":
        found: list[LiveEvent | LiveUsage] = [
            LiveText(
                str(event.get("transcript") or ""), LiveChannel.INPUT, final=True, item_id=item_id
            )
        ]
        usage = realtime_usage(event.get("usage"))
        return [*found, LiveUsage(usage)] if usage is not None else found
    if kind == "conversation.item.input_audio_transcription.failed":
        # Отказ одной фразы не рвёт сессию: остальные реплики встречи распознаются дальше.
        log.warning("Фраза живой расшифровки не распознана", item_id=item_id)
    elif kind == "error":
        error = event.get("error")
        code = error.get("code") if isinstance(error, dict) else None
        log.warning("OpenAI Realtime сообщил об ошибке", code=str(code))
    return []


class RealtimeTranscription:
    """One open transcription session."""

    def __init__(self, socket: ClientConnection) -> None:
        self._socket = socket
        self._closing = False

    @property
    def input_rate(self) -> int:
        """PCM16 mono at 24 kHz."""
        return INPUT_RATE

    async def send_audio(self, pcm: bytes) -> None:
        """Append audio to the session's buffer."""
        audio = base64.b64encode(pcm).decode("ascii")
        await self._send({"type": "input_audio_buffer.append", "audio": audio})

    async def end_turn(self) -> None:
        """Commit the buffer as a phrase."""
        await self._send({"type": "input_audio_buffer.commit"})

    async def send_tool_result(self, call: LiveToolCall, result: str) -> None:
        """A transcription session calls no tools."""
        raise AiCallError(AiFailure.MODEL_UNAVAILABLE)

    async def events(self) -> AsyncIterator[LiveEvent | LiveUsage]:
        """Texts and usage as they come; `LiveEnd` when the socket closes."""
        try:
            async for message in self._socket:
                try:
                    event = json.loads(message)
                except json.JSONDecodeError:
                    log.warning("OpenAI Realtime прислал не JSON")
                    continue
                if isinstance(event, dict):
                    for found in event_of(event):
                        yield found
        except ConnectionClosed:
            pass
        yield LiveEnd(None if self._closing else ended_by(self._socket))

    def floor(self, seconds: float) -> Usage:
        """Live transcription is billed by the second of audio."""
        return Usage(units=Decimal(str(round(seconds, 3))), unit=Unit.AUDIO_SECOND)

    async def close(self) -> None:
        """Close the socket."""
        self._closing = True
        await self._socket.close()

    async def _send(self, event: dict[str, Any]) -> None:
        try:
            await self._socket.send(json.dumps(event))
        except ConnectionClosed:
            raise AiCallError(AiFailure.PROVIDER_ERROR) from None


def ended_by(socket: ClientConnection) -> AiFailure:
    """Why the provider closed the socket: a rate or quota reason is a rate limit."""
    reason = (socket.close_reason or "").lower()
    if "rate" in reason or "quota" in reason:
        return AiFailure.RATE_LIMITED
    log.warning("OpenAI Realtime закрыл сессию", code=socket.close_code)
    return AiFailure.PROVIDER_ERROR


class OpenAiRealtime:
    """Opens transcription sessions with OpenAI's Realtime models."""

    def __init__(
        self, api_key: str, url: str = OPENAI_REALTIME, tls: ssl.SSLContext | None = None
    ) -> None:
        self._api_key = api_key
        self._url = url
        self._tls = tls

    async def connect(
        self, model: ModelRef, setup: LiveTranscriptionSetup
    ) -> RealtimeTranscription:
        """A session configured and confirmed by the provider."""
        try:
            socket = await connect(
                self._url,
                additional_headers={"Authorization": f"Bearer {self._api_key}"},
                max_size=MAX_MESSAGE_BYTES,
                close_timeout=1,
                ssl=self._tls,
            )
        except InvalidStatus as refused:
            raise AiCallError(failure_of(refused.response.status_code, "")) from None
        except OSError, WebSocketException:
            raise AiCallError(AiFailure.PROVIDER_ERROR) from None
        try:
            await socket.send(json.dumps(session_update(model.model, setup)))
            await confirmed(socket)
        except ConnectionClosed, AiCallError:
            await socket.close()
            raise AiCallError(AiFailure.PROVIDER_ERROR) from None
        return RealtimeTranscription(socket)


async def confirmed(socket: ClientConnection) -> None:
    """Wait for `session.updated`; an `error` first means the session was refused."""
    async for message in socket:
        try:
            event = json.loads(message)
        except json.JSONDecodeError:
            raise AiCallError(AiFailure.PROVIDER_ERROR) from None
        kind = event.get("type") if isinstance(event, dict) else None
        if kind == "session.updated":
            return
        if kind == "error":
            log.warning("OpenAI Realtime отклонил настройку сессии")
            raise AiCallError(AiFailure.PROVIDER_ERROR)
    raise AiCallError(AiFailure.PROVIDER_ERROR)
