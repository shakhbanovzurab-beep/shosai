"""What a model call returned and what it consumed (F6 plan §3.3, ADR 0035 point 6)."""

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from shosai.core.ai.calls import ModelRef
from shosai.core.ai.errors import AiFailure
from shosai.core.ai.requests import ToolCall


class Unit(StrEnum):
    """The units a price is set in (ADR 0035 point 3)."""

    # Токены: входные, входные из кэша провайдера, выходные.
    INPUT = "input_token"
    CACHED_INPUT = "cached_input_token"
    OUTPUT = "output_token"
    # Аудиотокены живых моделей стоят иначе, чем текстовые.
    INPUT_AUDIO = "input_audio_token"
    OUTPUT_AUDIO = "output_audio_token"
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
    input_audio_tokens: int = 0
    output_audio_tokens: int = 0
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
    """A piece of a streamed answer; the last one carries the usage of the whole call, and
    every one the model of the route that is answering."""

    text: str = ""
    finish_reason: str | None = None
    usage: Usage | None = None
    model: ModelRef | None = None


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


class LiveChannel(StrEnum):
    """Whose speech a live text is: the person's input or the model's spoken output."""

    INPUT = "input"
    OUTPUT = "output"


@dataclass(frozen=True, slots=True)
class LiveText:
    """Text of a live session; a final piece closes its item, earlier ones are partial."""

    text: str
    channel: LiveChannel
    final: bool
    item_id: str | None = None


@dataclass(frozen=True, slots=True)
class LiveAudio:
    """Speech the model produced: PCM16 mono at the given rate."""

    data: bytes
    sample_rate: int


@dataclass(frozen=True, slots=True)
class LiveToolCall:
    """A tool the model of a voice session asks to call; arguments are JSON."""

    call_id: str
    name: str
    arguments: str


@dataclass(frozen=True, slots=True)
class LiveUsage:
    """Usage the provider reported during a session; the port meters it, callers never see it."""

    usage: Usage


@dataclass(frozen=True, slots=True)
class LiveEnd:
    """The session is over: None when it was closed on purpose, else why it broke."""

    failure: AiFailure | None


type LiveEvent = LiveText | LiveAudio | LiveToolCall | LiveEnd
