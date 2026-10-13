"""What a model call returned and what it consumed (F6 plan §3.3, ADR 0035 point 6)."""

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from shosai.core.ai.calls import ModelRef
from shosai.core.ai.requests import ToolCall


class Unit(StrEnum):
    """The units a price is set in (ADR 0035 point 3)."""

    # Токены: входные, входные из кэша провайдера, выходные.
    INPUT = "input_token"
    CACHED_INPUT = "cached_input_token"
    OUTPUT = "output_token"
    AUDIO_SECOND = "audio_second"
    PAGE = "page"
    DOCUMENT = "document"
    REQUEST = "request"
    IMAGE = "image"


@dataclass(frozen=True, slots=True)
class Usage:
    """Tokens and other units a call consumed, and the cost the provider reported, if any."""

    input_tokens: int = 0
    cached_tokens: int = 0
    output_tokens: int = 0
    # Не токены: секунды, страницы, запросы, картинки — в своих единицах.
    units: Decimal = Decimal(0)
    unit: Unit | None = None
    reported_cost_usd: Decimal | None = None


@dataclass(frozen=True, slots=True)
class ChatResult:
    """The model's answer: its text, the tools it asked to call, and why it stopped."""

    text: str
    tool_calls: tuple[ToolCall, ...]
    finish_reason: str | None
    model: ModelRef
    usage: Usage


@dataclass(frozen=True, slots=True)
class ChatDelta:
    """A piece of a streamed answer; the last one carries the usage of the whole call."""

    text: str = ""
    finish_reason: str | None = None
    usage: Usage | None = None


@dataclass(frozen=True, slots=True)
class Embeddings:
    """One vector per text, in the order of the request."""

    vectors: tuple[tuple[float, ...], ...]
    model: ModelRef
    usage: Usage


@dataclass(frozen=True, slots=True)
class RankedDocument:
    """A document's position in the request and its relevance to the query."""

    index: int
    score: float


@dataclass(frozen=True, slots=True)
class Ranking:
    """The documents from the most relevant down."""

    documents: tuple[RankedDocument, ...]
    model: ModelRef
    usage: Usage


@dataclass(frozen=True, slots=True)
class GeneratedImage:
    """A generated picture as bytes and their media type."""

    data: bytes
    media_type: str
    model: ModelRef
    usage: Usage


@dataclass(frozen=True, slots=True)
class TranscriptSegment:
    """A stretch of speech: its time in the recording, its text and its speaker if known."""

    start_ms: int
    end_ms: int
    text: str
    speaker: int | None = None


@dataclass(frozen=True, slots=True)
class Transcript:
    """The text of a recording, in segments when the provider gives them."""

    text: str
    segments: tuple[TranscriptSegment, ...]
    language: str | None
    model: ModelRef
    usage: Usage


@dataclass(frozen=True, slots=True)
class SpeakerTurn:
    """When one speaker spoke; speakers are numbered 0..N-1 in order of first appearance."""

    start_ms: int
    end_ms: int
    speaker: int


@dataclass(frozen=True, slots=True)
class Diarization:
    """Who spoke when."""

    turns: tuple[SpeakerTurn, ...]
    model: ModelRef
    usage: Usage
