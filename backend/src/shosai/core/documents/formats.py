"""What a file is, by its bytes: an image, a document whose text can be read, or neither.

The bytes decide, never the name — except to tell apart the office formats, which are all ZIP
containers, and to admit plain text and data formats, which have no signature. A file nothing
admits is rejected before any parser sees it.
"""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePath
from typing import Final


class DocumentFormat(StrEnum):
    """A format whose text the platform reads."""

    PDF = "pdf"
    DOCX = "docx"
    XLSX = "xlsx"
    PPTX = "pptx"
    RTF = "rtf"
    TEXT = "text"


class FileKind(StrEnum):
    """What a file is for a reader."""

    IMAGE = "image"
    DOCUMENT = "document"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class Sniffed:
    """A file's kind and, for an image, its media type; for a document, its format."""

    kind: FileKind
    media_type: str | None = None
    document: DocumentFormat | None = None


REJECTED: Final = Sniffed(FileKind.REJECTED)
OFFICE: Final = {
    ".docx": DocumentFormat.DOCX,
    ".xlsx": DocumentFormat.XLSX,
    ".pptx": DocumentFormat.PPTX,
}
TEXT_SUFFIXES: Final = frozenset(
    {".txt", ".md", ".markdown", ".csv", ".json", ".xml", ".yaml", ".yml"}
)
SIGNED: Final = ((b"%PDF", DocumentFormat.PDF), (b"{\\rtf", DocumentFormat.RTF))
HEIF_BRANDS: Final = frozenset({b"heic", b"heix", b"hevc", b"hevx", b"mif1", b"msf1", b"heif"})


def image_type(data: bytes) -> str | None:
    """The media type of a raster image by its signature, or None."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data[:6] in {b"GIF87a", b"GIF89a"}:
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[4:8] == b"ftyp" and data[8:12] in HEIF_BRANDS:
        return "image/heic"
    return None


def utf8(data: bytes) -> bool:
    """Whether the bytes are UTF-8 text."""
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def sniff(filename: str, data: bytes) -> Sniffed:
    """What the file is, by its bytes; its name only tells the office formats apart."""
    media_type = image_type(data)
    if media_type is not None:
        return Sniffed(FileKind.IMAGE, media_type=media_type)
    document = document_format(PurePath(filename.lower()).suffix, data)
    return REJECTED if document is None else Sniffed(FileKind.DOCUMENT, document=document)


def document_format(suffix: str, data: bytes) -> DocumentFormat | None:
    """The document format of the bytes, or None for anything else."""
    signed = next((fmt for signature, fmt in SIGNED if data.startswith(signature)), None)
    if signed is not None:
        return signed
    if data.startswith(b"PK\x03\x04"):
        return OFFICE.get(suffix)
    if data and suffix in TEXT_SUFFIXES and utf8(data):
        return DocumentFormat.TEXT
    return None
