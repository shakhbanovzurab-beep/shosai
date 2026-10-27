"""OpenRouter's speech-to-text wire format, as pure functions (no network).

Facts from OpenRouter's documentation (`/docs/guides/overview/multimodal/stt`, read on
2026-10-13 and 2026-10-27) and the pilot of 2026-10-27 (ADR 0073):

- `POST /audio/transcriptions` takes JSON: `model`, `input_audio {data, format}` with the
  audio base64-encoded, optional `language`, `temperature`, `response_format`
- `format` is one of wav, mp3, flac, m4a, ogg, webm, aac; support varies by provider
- the answer is `{text, usage {seconds, input_tokens, output_tokens, cost}}`; `verbose_json`
  adds `language` and `segments` with `start`, `end` in seconds and a `speaker` index when
  the provider diarizes; some models reject `verbose_json` with 400
- `timestamp_granularities` with `word` adds `words`, each with its `speaker` where the
  provider gives one; ElevenLabs' Scribe answers one segment for the whole file, so its
  speakers are read from the words
- a provider's own options go in `provider.options.<slug>`; only the serving provider's are
  forwarded, so asking every diarizing provider for speakers is harmless to the others
- the audio may be at most 25 MB: the limit is the file's, not its base64's (a 31.7 MB body
  of 22.7 MB of audio was accepted); the documentation names a 60-second upstream timeout,
  yet 99 minutes of audio were answered in 80 s, so recordings go in parts of 90 minutes
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
# Опции провайдеров, которые сами размечают говорящих: ключ — слаг провайдера в OpenRouter.
SPEAKER_OPTIONS: Final[Json] = {"elevenlabs": {"diarize": True, "tag_audio_events": False}}
# Пауза, после которой слова одного голоса — уже другой сегмент.
WORD_GAP_MS: Final = 800


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
    if request.speakers:
        body["response_format"] = "verbose_json"
        body["timestamp_granularities"] = ["segment", "word"]
        body["provider"] = {"options": SPEAKER_OPTIONS}
    elif request.timestamps:
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


def speaker_segments(text: str, raw: object) -> tuple[TranscriptSegment, ...]:
    """Segments from the words that carry speakers: one per run of a voice, broken at a pause.

    Each segment's text is cut from the answer's text between its first and last word, so
    the spacing of scripts written without spaces is kept. Empty when no word has a speaker;
    a malformed word is a provider error.
    """
    if not isinstance(raw, list):
        return ()
    words = [_word(item) for item in raw]
    spoken = [word for word in words if word[2].strip()]
    if not spoken or all(speaker is None for *_, speaker in spoken):
        return ()
    runs: list[list[tuple[int, int, str, int | None]]] = []
    for word in spoken:
        last = runs[-1][-1] if runs else None
        if last is None or word[3] != last[3] or word[0] - last[1] > WORD_GAP_MS:
            runs.append([word])
        else:
            runs[-1].append(word)
    return tuple(_segment(text, run, at) for run, at in _placed(text, runs))


def _word(item: object) -> tuple[int, int, str, int | None]:
    start = item.get("start") if isinstance(item, dict) else None
    end = item.get("end") if isinstance(item, dict) else None
    word = item.get("word") if isinstance(item, dict) else None
    if not isinstance(start, int | float) or not isinstance(end, int | float) or end < start:
        raise AiCallError(AiFailure.PROVIDER_ERROR)
    if not isinstance(word, str):
        raise AiCallError(AiFailure.PROVIDER_ERROR)
    speaker = item.get("speaker") if isinstance(item, dict) else None
    known = speaker if isinstance(speaker, int) and speaker >= 0 else None
    return round(start * 1000), round(end * 1000), word, known


def _placed(
    text: str, runs: list[list[tuple[int, int, str, int | None]]]
) -> list[tuple[list[tuple[int, int, str, int | None]], tuple[int, int] | None]]:
    """Each run with where its words lie in the text, or None when a word is not found."""
    cursor = 0
    placed: list[tuple[list[tuple[int, int, str, int | None]], tuple[int, int] | None]] = []
    for run in runs:
        begin = end = None
        for _, _, word, _ in run:
            found = text.find(word, cursor)
            if found < 0:
                begin = None
                break
            begin = found if begin is None else begin
            end = cursor = found + len(word)
        placed.append((run, (begin, end) if begin is not None and end is not None else None))
    return placed


def _segment(
    text: str, run: list[tuple[int, int, str, int | None]], at: tuple[int, int] | None
) -> TranscriptSegment:
    # Слово, которого нет в тексте ответа, — склейка через пробел: текст не теряется.
    said = text[at[0] : at[1]] if at is not None else " ".join(word for _, _, word, _ in run)
    return TranscriptSegment(
        start_ms=run[0][0], end_ms=max(word[1] for word in run), text=said.strip(),
        speaker=run[0][3],
    )  # fmt: skip
