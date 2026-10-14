"""What a call is expected to consume, before it is sent: the amount it reserves (§3.6).

An estimate errs high, never low: it reserves room under the ceilings, and the recorded
cost replaces it. Text counts four characters a token; an image 765 input tokens (a 512-px
tile of the vision models); output is the request's own bound. Speech counts its seconds
and, for token-billed models, 10 input and 3 output tokens a second; a live minute 25 audio
tokens a second each way. A document whose pages are not named counts a page per 150 KB.
"""

import json
import math
from decimal import Decimal
from typing import Final

from shosai.core.ai.decisions import DecisionRequest
from shosai.core.ai.documents import OcrRequest
from shosai.core.ai.requests import (
    AudioFile,
    ChatRequest,
    EmbeddingRequest,
    ImagePart,
    TextPart,
)
from shosai.core.ai.results import Unit, Usage

CHARS_PER_TOKEN: Final = 4
IMAGE_TOKENS: Final = 765
SPEECH_IN_TOKENS: Final = 10
SPEECH_OUT_TOKENS: Final = 3
AUDIO_TOKENS: Final = 25
BYTES_PER_PAGE: Final = 150_000
LIVE_MINUTE: Final = 60


def tokens_of(text: str) -> int:
    """Tokens of a text, rounded up."""
    return math.ceil(len(text) / CHARS_PER_TOKEN)


def chat_estimate(request: ChatRequest) -> Usage:
    """Input of every message and image, and the whole output bound."""
    parts = [part for message in request.messages for part in message.parts]
    text = sum(tokens_of(part.text) for part in parts if isinstance(part, TextPart))
    images = sum(1 for part in parts if isinstance(part, ImagePart))
    return Usage(input_tokens=text + images * IMAGE_TOKENS, output_tokens=request.max_output_tokens)


def embedding_estimate(request: EmbeddingRequest) -> Usage:
    """Input of every text."""
    return Usage(input_tokens=sum(tokens_of(text) for text in request.texts))


def per_item(unit: Unit) -> Usage:
    """One request or one picture."""
    return Usage(units=Decimal(1), unit=unit)


def speech_estimate(audio: AudioFile) -> Usage:
    """The recording's seconds, and its tokens for a token-billed model."""
    seconds = Decimal(str(audio.duration_seconds))
    return Usage(
        input_tokens=math.ceil(audio.duration_seconds * SPEECH_IN_TOKENS),
        output_tokens=math.ceil(audio.duration_seconds * SPEECH_OUT_TOKENS),
        units=seconds,
        unit=Unit.AUDIO_SECOND,
    )


def decision_estimate(request: DecisionRequest) -> Usage:
    """The state and every question's text; Jev's output is free."""
    state = request.state if isinstance(request.state, str) else json.dumps(dict(request.state))
    questions = json.dumps({name: repr(question) for name, question in request.questions.items()})
    return Usage(input_tokens=tokens_of(state) + tokens_of(questions))


def ocr_estimate(request: OcrRequest) -> Usage:
    """The named pages, or a page per 150 KB of the document."""
    pages = len(request.pages) or max(1, math.ceil(len(request.data) / BYTES_PER_PAGE))
    return Usage(units=Decimal(pages), unit=Unit.PAGE)


def live_minute() -> Usage:
    """A minute of a live session, in seconds and in audio tokens both ways."""
    return Usage(
        input_audio_tokens=LIVE_MINUTE * AUDIO_TOKENS,
        output_audio_tokens=LIVE_MINUTE * AUDIO_TOKENS,
        units=Decimal(LIVE_MINUTE),
        unit=Unit.AUDIO_SECOND,
    )
