"""What a file is, from its name: the cabinet's kinds and what Leo can read (`files.ts`).

The kind follows the extension; Leo reads nine extensions up to 50 MiB, judged by the end
of the name in lower case exactly as the cabinet does.
"""

from enum import StrEnum
from typing import Final

LEO_MAX_FILE_BYTES: Final = 50 * 1024**2
LEO_EXTENSIONS: Final = (".pdf", ".docx", ".pptx", ".xlsx", ".csv", ".txt", ".md", ".html", ".json")


class FileKind(StrEnum):
    """The cabinet's kinds of files."""

    DOCUMENT = "document"
    SPREADSHEET = "spreadsheet"
    PRESENTATION = "presentation"
    PDF = "pdf"
    TEXT = "text"
    DESIGN = "design"
    IMAGE = "image"
    ARCHIVE = "archive"
    OTHER = "other"


KIND_BY_EXTENSION: Final = {
    "pdf": FileKind.PDF,
    "doc": FileKind.DOCUMENT,
    "docx": FileKind.DOCUMENT,
    "xls": FileKind.SPREADSHEET,
    "xlsx": FileKind.SPREADSHEET,
    "csv": FileKind.SPREADSHEET,
    "ppt": FileKind.PRESENTATION,
    "pptx": FileKind.PRESENTATION,
    "md": FileKind.TEXT,
    "txt": FileKind.TEXT,
    "html": FileKind.TEXT,
    "json": FileKind.TEXT,
    "fig": FileKind.DESIGN,
    "sketch": FileKind.DESIGN,
    "png": FileKind.IMAGE,
    "jpg": FileKind.IMAGE,
    "jpeg": FileKind.IMAGE,
    "svg": FileKind.IMAGE,
    "zip": FileKind.ARCHIVE,
    "rar": FileKind.ARCHIVE,
}
# Активное содержимое браузер исполнил бы на домене бакета: только скачивание (урок черновика).
ACTIVE_CONTENT_TYPES: Final = frozenset(
    {
        "text/html",
        "image/svg+xml",
        "application/xhtml+xml",
        "text/javascript",
        "application/javascript",
        "application/xml",
        "text/xml",
    }
)


def extension_of(name: str) -> str:
    """The extension in lower case, without the dot; empty when there is none."""
    dot = name.rfind(".")
    return name[dot + 1 :].lower() if dot > 0 else ""


def kind_of(name: str) -> FileKind:
    """The cabinet's kind of a file by its name."""
    return KIND_BY_EXTENSION.get(extension_of(name), FileKind.OTHER)


def leo_readable(name: str, size_bytes: int) -> bool:
    """Whether Leo can read the file at all: a supported extension, up to 50 MiB."""
    lowered = name.lower()
    return size_bytes <= LEO_MAX_FILE_BYTES and any(lowered.endswith(ext) for ext in LEO_EXTENSIONS)


def opens_inline(content_type: str) -> bool:
    """Whether a download may open in the browser; active content is always an attachment."""
    return content_type.split(";", 1)[0].strip().lower() not in ACTIVE_CONTENT_TYPES
