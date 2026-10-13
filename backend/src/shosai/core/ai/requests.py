"""What a caller asks a model for (F6 plan §3.3). Value types only, no client or framework."""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Final

MAX_IMAGE_BYTES: Final = 8 * 1024 * 1024


class Role(StrEnum):
    """Who wrote a message of the conversation."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass(frozen=True, slots=True)
class TextPart:
    """Text in a message."""

    text: str


@dataclass(frozen=True, slots=True)
class ImagePart:
    """An image in a message, as bytes and their media type."""

    data: bytes
    media_type: str

    def __post_init__(self) -> None:
        if not self.media_type.startswith("image/") or not self.data:
            message = "картинка сообщения — непустые байты с типом image/*"
            raise ValueError(message)
        if len(self.data) > MAX_IMAGE_BYTES:
            message = "картинка сообщения — не больше 8 МБ"
            raise ValueError(message)


type ContentPart = TextPart | ImagePart


@dataclass(frozen=True, slots=True)
class ToolCall:
    """A tool the model asked to call, with its arguments as the model wrote them (JSON)."""

    call_id: str
    name: str
    arguments: str


@dataclass(frozen=True, slots=True)
class ChatMessage:
    """One message: its role, its parts, and for the assistant's tool turns their calls."""

    role: Role
    parts: tuple[ContentPart, ...] = ()
    tool_calls: tuple[ToolCall, ...] = ()
    # Ответ инструмента ссылается на вызов, на который отвечает.
    tool_call_id: str | None = None


@dataclass(frozen=True, slots=True)
class ToolSchema:
    """A tool the model may call: its name, English description and JSON schema of arguments."""

    name: str
    description: str
    parameters: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ChatRequest:
    """A conversation for a chat model and how to answer it."""

    messages: tuple[ChatMessage, ...]
    max_output_tokens: int
    temperature: float | None = None
    tools: tuple[ToolSchema, ...] = ()
    # Серверный инструмент OpenRouter: поиск в сети с ссылками на источники.
    web_search_results: int = 0

    def __post_init__(self) -> None:
        if not self.messages:
            message = "запрос к чату — хотя бы одно сообщение"
            raise ValueError(message)
        if self.max_output_tokens < 1:
            message = "предел ответа — хотя бы один токен"
            raise ValueError(message)
        if not 0 <= self.web_search_results <= 10:
            message = "результатов веб-поиска — от 0 до 10"
            raise ValueError(message)


@dataclass(frozen=True, slots=True)
class EmbeddingRequest:
    """Texts to embed, in order."""

    texts: tuple[str, ...]
    dimensions: int | None = None

    def __post_init__(self) -> None:
        if not self.texts:
            message = "эмбеддинги — хотя бы один текст"
            raise ValueError(message)


@dataclass(frozen=True, slots=True)
class RerankRequest:
    """Documents to order by their relevance to a query."""

    query: str
    documents: tuple[str, ...]
    top_n: int | None = None

    def __post_init__(self) -> None:
        if not self.documents:
            message = "переранжирование — хотя бы один документ"
            raise ValueError(message)


@dataclass(frozen=True, slots=True)
class ImageRequest:
    """A picture to generate from a prompt, optionally from reference images."""

    prompt: str
    references: tuple[ImagePart, ...] = field(default=())
