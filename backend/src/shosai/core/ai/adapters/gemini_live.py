"""Google Gemini Live: simultaneous translation and the voice assistant (ADR 0043).

Through the google-genai client (§18.2), server to server with the API key. Facts from
Google's documentation (Live API, live translate guide and pricing, read on 2026-10-13):

- input is PCM16 mono at 16 kHz, output speech PCM16 at 24 kHz
- a translation model (`gemini-3.5-live-translate-preview`) takes `translationConfig` with
  the target language and translates as the speaker talks; it takes no instruction, voice
  or tools
- a conversational model (`gemini-3.8-live`) interprets by an instruction with a chosen
  voice, waiting for the speaker's pause, and calls tools
- `usageMetadata` counts tokens per modality; audio is counted at 25 tokens per second
- `receive()` of the client ends after each turn and is called again for the next one
"""

import json
import math
import ssl
from collections.abc import AsyncIterator, Awaitable
from contextlib import AsyncExitStack
from typing import Final

import structlog
from google import genai
from google.genai import errors, types
from websockets.exceptions import WebSocketException

from shosai.core.ai.calls import ModelRef
from shosai.core.ai.errors import AiCallError, AiFailure
from shosai.core.ai.requests import NativeTranslationSetup, VoiceSetup
from shosai.core.ai.results import (
    LiveAudio,
    LiveChannel,
    LiveEnd,
    LiveEvent,
    LiveText,
    LiveToolCall,
    LiveUsage,
    Usage,
)

GEMINI_API: Final = "https://generativelanguage.googleapis.com"
INPUT_RATE: Final = 16_000
OUTPUT_RATE: Final = 24_000
AUDIO_TOKENS_PER_SECOND: Final = 25
INPUT_AUDIO: Final = f"audio/pcm;rate={INPUT_RATE}"
log = structlog.stdlib.get_logger(__name__)


def gemini_client(
    api_key: str, base_url: str = GEMINI_API, tls: ssl.SSLContext | None = None
) -> genai.Client:
    """The process's Gemini client; `tls` replaces the trusted roots, for a local server."""
    options = types.HttpOptions(base_url=base_url, api_version="v1beta")
    if tls is not None:
        options.async_client_args = {"ssl": tls}
    return genai.Client(api_key=api_key, http_options=options)


def live_config(setup: NativeTranslationSetup | VoiceSetup) -> types.LiveConnectConfig:
    """The session's configuration: transcripts of both sides are always on."""
    config = types.LiveConnectConfig(
        response_modalities=[types.Modality.AUDIO],
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
    )
    if isinstance(setup, NativeTranslationSetup):
        config.translation_config = types.TranslationConfig(
            target_language_code=setup.target_language,
            echo_target_language=setup.echo_target_language,
        )
        return config
    config.system_instruction = setup.instruction
    config.speech_config = types.SpeechConfig(
        voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=setup.voice)
        )
    )
    config.realtime_input_config = types.RealtimeInputConfig(
        automatic_activity_detection=types.AutomaticActivityDetection(
            silence_duration_ms=setup.silence_ms
        )
    )
    if setup.tools:
        declarations = [
            types.FunctionDeclaration(
                name=tool.name, description=tool.description, parameters_json_schema=tool.parameters
            )
            for tool in setup.tools
        ]
        config.tools = [types.Tool(function_declarations=declarations)]
    return config


def usage_of(metadata: types.UsageMetadata) -> Usage:
    """Tokens of one report, split into audio and the rest, on the way in and out."""
    counts = {"in_audio": 0, "in_other": 0, "out_audio": 0, "out_other": 0}
    for side, details in (
        ("in", metadata.prompt_tokens_details),
        ("out", metadata.response_tokens_details),
    ):
        for detail in details or ():
            audio = detail.modality == types.MediaModality.AUDIO
            counts[f"{side}_{'audio' if audio else 'other'}"] += detail.token_count or 0
    return Usage(
        input_tokens=counts["in_other"],
        input_audio_tokens=counts["in_audio"],
        output_tokens=counts["out_other"],
        output_audio_tokens=counts["out_audio"],
    )


def texts_of(content: types.LiveServerContent) -> list[LiveEvent | LiveUsage]:
    """Transcript pieces of both sides; a finished one closes its side's text."""
    found: list[LiveEvent | LiveUsage] = []
    for channel, piece in (
        (LiveChannel.INPUT, content.input_transcription),
        (LiveChannel.OUTPUT, content.output_transcription),
    ):
        if piece is not None and (piece.text or piece.finished):
            found.append(LiveText(piece.text or "", channel, final=bool(piece.finished)))
    return found


def speech_of(content: types.LiveServerContent) -> list[LiveEvent | LiveUsage]:
    """The model's speech in the turn."""
    parts = content.model_turn.parts if content.model_turn else None
    return [
        LiveAudio(part.inline_data.data, OUTPUT_RATE)
        for part in parts or ()
        if part.inline_data is not None and part.inline_data.data
    ]


def tool_calls_of(call: types.LiveServerToolCall) -> list[LiveEvent | LiveUsage]:
    """The tools the model asks to call, with JSON arguments."""
    return [
        LiveToolCall(
            item.id or "", item.name or "", json.dumps(item.args or {}, ensure_ascii=False)
        )
        for item in call.function_calls or ()
    ]


def events_of(message: types.LiveServerMessage) -> list[LiveEvent | LiveUsage]:
    """What one server message means for the session."""
    found: list[LiveEvent | LiveUsage] = []
    if message.server_content is not None:
        found += texts_of(message.server_content) + speech_of(message.server_content)
    if message.tool_call is not None:
        found += tool_calls_of(message.tool_call)
    if message.usage_metadata is not None:
        found.append(LiveUsage(usage_of(message.usage_metadata)))
    if message.go_away is not None:
        log.info("Gemini Live скоро закроет сессию", time_left=str(message.go_away.time_left))
    return found


def failure_of(error: errors.APIError) -> AiFailure:
    """The failure a closed Live socket or a refused setup means."""
    text = f"{error.status} {error.message}".lower()
    if error.code == 429 or "resource_exhausted" in text or "quota" in text:
        return AiFailure.RATE_LIMITED
    if error.code == 404 or "not found" in text:
        return AiFailure.MODEL_UNAVAILABLE
    return AiFailure.PROVIDER_ERROR


class GeminiSession:
    """One open Live session."""

    def __init__(self, session: genai.live.AsyncSession, stack: AsyncExitStack) -> None:
        self._session = session
        self._stack = stack
        self._closing = False

    @property
    def input_rate(self) -> int:
        """PCM16 mono at 16 kHz."""
        return INPUT_RATE

    async def send_audio(self, pcm: bytes) -> None:
        """Stream a piece of audio."""
        await self._guarded(
            self._session.send_realtime_input(audio=types.Blob(data=pcm, mime_type=INPUT_AUDIO))
        )

    async def end_turn(self) -> None:
        """Tell the model the audio stream paused."""
        await self._guarded(self._session.send_realtime_input(audio_stream_end=True))

    async def send_tool_result(self, call: LiveToolCall, result: str) -> None:
        """Answer the model's tool call with a JSON result."""
        response = types.FunctionResponse(
            id=call.call_id, name=call.name, response=json.loads(result)
        )
        await self._guarded(self._session.send_tool_response(function_responses=[response]))

    async def events(self) -> AsyncIterator[LiveEvent | LiveUsage]:
        """Text, speech, tool calls and usage; `LiveEnd` when the socket closes."""
        failure: AiFailure | None = None
        try:
            while True:
                async for message in self._session.receive():
                    for event in events_of(message):
                        yield event
        except errors.APIError as error:
            failure = None if self._closing else failure_of(error)
        except WebSocketException:
            failure = None if self._closing else AiFailure.PROVIDER_ERROR
        if failure is not None:
            log.warning("Сессия Gemini Live оборвалась", failure=failure.value)
        yield LiveEnd(failure)

    def floor(self, seconds: float) -> Usage:
        """Input audio is billed at 25 tokens per second, silence included."""
        return Usage(input_audio_tokens=math.ceil(seconds * AUDIO_TOKENS_PER_SECOND))

    async def close(self) -> None:
        """Close the socket."""
        self._closing = True
        await self._stack.aclose()

    async def _guarded(self, sending: Awaitable[None]) -> None:
        try:
            await sending
        except errors.APIError, WebSocketException:
            raise AiCallError(AiFailure.PROVIDER_ERROR) from None


class GeminiLive:
    """Opens Live sessions with Google's models."""

    def __init__(self, client: genai.Client) -> None:
        self._client = client

    async def connect(
        self, model: ModelRef, setup: NativeTranslationSetup | VoiceSetup
    ) -> GeminiSession:
        """A session the provider accepted."""
        stack = AsyncExitStack()
        try:
            session = await stack.enter_async_context(
                self._client.aio.live.connect(model=model.model, config=live_config(setup))
            )
        except errors.APIError as error:
            await stack.aclose()
            raise AiCallError(failure_of(error)) from None
        except OSError, WebSocketException:
            await stack.aclose()
            raise AiCallError(AiFailure.PROVIDER_ERROR) from None
        return GeminiSession(session, stack)
