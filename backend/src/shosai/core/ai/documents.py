"""Documents read by OCR: the request and the pages read. Value types only."""

from dataclasses import dataclass
from typing import Final

from shosai.core.ai.calls import ModelRef
from shosai.core.ai.results import Usage

# Документ едет в теле запроса base64, на треть тяжелее: 25 МБ проверены черновиком.
OCR_MAX_BYTES: Final = 25 * 1024 * 1024
OCR_MEDIA_TYPES: Final = frozenset(
    {"application/pdf", "image/png", "image/jpeg", "image/webp", "image/gif", "image/tiff"}
)


@dataclass(frozen=True, slots=True)
class OcrRequest:
    """A scanned PDF or an image to read; `pages` limits a PDF to those pages, from 0."""

    data: bytes
    media_type: str
    pages: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if not self.data or len(self.data) > OCR_MAX_BYTES:
            message = "документ для OCR — непустой, до 25 МБ"
            raise ValueError(message)
        if self.media_type not in OCR_MEDIA_TYPES:
            message = "OCR читает PDF и картинки"
            raise ValueError(message)
        if any(page < 0 for page in self.pages):
            message = "страницы считаются с нуля"
            raise ValueError(message)


@dataclass(frozen=True, slots=True)
class OcrPage:
    """One page read: its position, its text as Markdown and its size in pixels."""

    index: int
    markdown: str
    width: int | None
    height: int | None


@dataclass(frozen=True, slots=True)
class OcrPages:
    """The pages read, in order, and the pages billed."""

    pages: tuple[OcrPage, ...]
    model: ModelRef
    usage: Usage
