"""Transcription answers as Scribe gives them through OpenRouter (ADR 0073), for the benches.

Scribe answers one segment for the whole file and marks each word with its voice; a model
that does not diarize answers timed segments without voices.
"""

import base64
from collections.abc import Callable
from typing import Any

import httpx

type Said = tuple[float, float, int | None, str]
# Гранула Ogg Opus считается в отсчётах 48 кГц, какой бы ни была частота записи.
OPUS_GRANULE_RATE = 48_000


def scribe(*said: Said, seconds: float = 150.0) -> httpx.Response:
    """An answer as Scribe gives it: one segment, each sentence's words with its voice."""
    words = []
    for start, end, voice, sentence in said:
        parts = sentence.split()
        step = (end - start) / len(parts)
        words += [
            {"word": word, "start": start + n * step, "end": start + (n + 1) * step,
             "speaker": voice}
            for n, word in enumerate(parts)
        ]  # fmt: skip
    text = " ".join(sentence for *_, sentence in said)
    return httpx.Response(
        200,
        json={
            "text": text, "language": "eng", "words": words,
            "segments": [{"start": 0.0, "end": said[-1][1] if said else 0.0, "text": text}],
            "usage": {"seconds": seconds, "cost": 0.009},
        },
    )  # fmt: skip


def unmarked(*said: tuple[float, float, str], seconds: float = 150.0) -> httpx.Response:
    """An answer of a model that marks no speakers: timed segments only."""
    segments = [{"start": start, "end": end, "text": text} for start, end, text in said]
    return httpx.Response(
        200,
        json={
            "text": " ".join(text for *_, text in said), "language": "english",
            "segments": segments, "usage": {"seconds": seconds, "cost": 0.0011},
        },
    )  # fmt: skip


def by_length(
    seconds: float, shorter: httpx.Response, longer: httpx.Response
) -> Callable[[dict[str, Any]], httpx.Response]:
    """A responder answering a part by its audio's length: parts are sent at once.

    The length is the last Ogg page's granule position, as the stage's Opus parts carry it.
    """

    def answer(body: dict[str, Any]) -> httpx.Response:
        audio = base64.b64decode(body["input_audio"]["data"])
        last = audio.rfind(b"OggS")
        granule = int.from_bytes(audio[last + 6 : last + 14], "little")
        return longer if granule / OPUS_GRANULE_RATE > seconds else shorter

    return answer
