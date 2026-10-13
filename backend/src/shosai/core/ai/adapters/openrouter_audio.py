"""OpenRouter's speech-to-text wire format, as pure functions (no network).

Facts from OpenRouter's documentation (`/docs/guides/overview/multimodal/stt`, read on
2026-10-13):

- `POST /audio/transcriptions` takes JSON: `model`, `input_audio {data, format}` with the
  audio base64-encoded, optional `language`, `temperature`, `response_format`
- `format` is one of wav, mp3, flac, m4a, ogg, webm, aac; support varies by provider
- the answer is `{text, usage {seconds, input_tokens, output_tokens, cost}}`; `verbose_json`
  adds `language` and `segments` with `start`, `end` in seconds and a `speaker` index when
  the provider diarizes; some models reject `verbose_json` with 400
- requests over 25 MB are rejected; the upstream provider times out after 60 s, so long
  recordings are cut into parts by the caller
"""

import base64
from decimal import Decimal
from typing import Final

from shosai.core.ai.adapters.audio_formats import audio_format
from shosai.core.ai.adapters.http_calls import Json
from shosai.core.ai.adapters.openrouter_wire import reported_cost
from shosai.core.ai.errors import AiCallError, AiFailure
from shosai.core.ai.requests import TranscriptionRequest
from shosai.core.ai.results import TranscriptSegment, Unit, Usage

MAX_AUDIO_BYTES: Final = 25 * 1024 * 1024


def transcription_body(model: str, request: TranscriptionRequest) -> Json:
    """The body of `/audio/transcriptions`; a refusal when the recording cannot be sent."""
    audio = request.audio
    if len(audio.data) > MAX_AUDIO_BYTES:
        raise AiCallError(AiFailure.CONTEXT_LENGTH_EXCEEDED)
    format_name = audio_format(audio.media_type)
    if format_name is None:
        raise AiCallError(AiFailure.CONTENT_REFUSED)
    body: Json = {
        "model": model,
        "input_audio": {
            "data": base64.b64encode(audio.data).decode("ascii"),
            "format": format_name,
        },
        "temperature": 0,
        "response_format": "verbose_json" if request.timestamps else "json",
    }
    if request.timestamps:
        body["timestamp_granularities"] = ["segment"]
    if request.language:
        body["language"] = request.language
    return body


def transcription_usage(raw: object) -> Usage:
    """Usage of a transcription: tokens, seconds of audio, and the cost OpenRouter charged."""
    usage = raw if isinstance(raw, dict) else {}
    seconds = usage.get("seconds")
    return Usage(
        input_tokens=int(usage.get("input_tokens") or 0),
        output_tokens=int(usage.get("output_tokens") or 0),
        units=Decimal(str(seconds)) if isinstance(seconds, int | float) else Decimal(0),
        unit=Unit.AUDIO_SECOND if isinstance(seconds, int | float) else None,
        reported_cost_usd=reported_cost(usage.get("cost")),
    )


def transcript_text(answer: Json) -> str:
    """The text of the recording, or a provider error."""
    text = answer.get("text")
    if not isinstance(text, str):
        raise AiCallError(AiFailure.PROVIDER_ERROR)
    return text.strip()


def segments_of(raw: object) -> tuple[TranscriptSegment, ...]:
    """Timed segments of a `verbose_json` answer; a malformed one is a provider error."""
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise AiCallError(AiFailure.PROVIDER_ERROR)
    segments = []
    for item in raw:
        start = item.get("start") if isinstance(item, dict) else None
        end = item.get("end") if isinstance(item, dict) else None
        if not isinstance(start, int | float) or not isinstance(end, int | float) or end < start:
            raise AiCallError(AiFailure.PROVIDER_ERROR)
        speaker = item.get("speaker")
        segments.append(
            TranscriptSegment(
                start_ms=round(start * 1000),
                end_ms=round(end * 1000),
                text=str(item.get("text") or "").strip(),
                speaker=speaker if isinstance(speaker, int) and speaker >= 0 else None,
            )
        )
    return tuple(segments)
