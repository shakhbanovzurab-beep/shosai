"""A document's text, read inside the extraction child (`core/documents/child.py`).

Each reader yields its text in pieces and stops at its own caps — pages, sheets, rows, slides —
while the collector stops at the character limit, so a large document costs no more than its
first part. An office file is a ZIP whose entries are checked before it is opened: a bomb is
refused unread.
"""

import io
import zipfile
from collections.abc import Callable, Iterable, Iterator
from typing import Final

from shosai.core.documents.formats import DocumentFormat

MAX_PDF_PAGES: Final = 500
MAX_SHEETS: Final = 20
MAX_ROWS: Final = 2_000
MAX_SLIDES: Final = 200
# Распакованный офисный файл: записей, байт всего и сжатие одной записи.
ZIP_MAX_ENTRIES: Final = 10_000
ZIP_MAX_BYTES: Final = 200 * 1024**2
ZIP_MAX_RATIO: Final = 100
# Запись меньше этого не проверяется на сжатие: у маленьких XML оно бывает огромным.
ZIP_RATIO_FLOOR: Final = 1024**2


class UnreadableError(Exception):
    """The document cannot be read; `code` says why, for the caller's step."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def collected(pieces: Iterable[str], limit: int) -> tuple[str, bool]:
    """The pieces joined up to `limit` characters; whether the text was cut there."""
    parts: list[str] = []
    size = 0
    for piece in pieces:
        room = limit - size
        if len(piece) >= room:
            parts.append(piece[:room])
            return "".join(parts), True
        parts.append(piece)
        size += len(piece)
    return "".join(parts), False


def checked_zip(data: bytes) -> None:
    """Refuse an office file whose ZIP would unpack too large or too many."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
    except zipfile.BadZipFile as error:
        raise UnreadableError("malformed") from error
    total = sum(entry.file_size for entry in entries)
    swollen = any(
        entry.file_size >= ZIP_RATIO_FLOOR
        and entry.file_size > ZIP_MAX_RATIO * max(entry.compress_size, 1)
        for entry in entries
    )
    if len(entries) > ZIP_MAX_ENTRIES or total > ZIP_MAX_BYTES or swollen:
        raise UnreadableError("too_large")


def pdf_text(data: bytes) -> Iterator[str]:
    """The text of a PDF's first pages."""
    from pypdf import PdfReader  # noqa: PLC0415 — грузится только в дочернем процессе

    reader = PdfReader(io.BytesIO(data))
    if reader.is_encrypted and not reader.decrypt(""):
        raise UnreadableError("encrypted")
    for page in reader.pages[:MAX_PDF_PAGES]:
        yield (page.extract_text() or "") + "\n"


def docx_text(data: bytes) -> Iterator[str]:
    """The paragraphs and table cells of a Word document."""
    import docx  # noqa: PLC0415 — тяжёлый разборщик грузится только в дочернем процессе

    checked_zip(data)
    document = docx.Document(io.BytesIO(data))
    for paragraph in document.paragraphs:
        yield paragraph.text + "\n"
    for table in document.tables:
        for row in table.rows:
            yield "\t".join(cell.text for cell in row.cells) + "\n"


def xlsx_text(data: bytes) -> Iterator[str]:
    """The first rows of an Excel workbook's first sheets, as tab-separated lines."""
    from openpyxl import load_workbook  # noqa: PLC0415 — грузится только в дочернем процессе

    checked_zip(data)
    workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    for sheet in workbook.worksheets[:MAX_SHEETS]:
        yield f"# {sheet.title}\n"
        for index, row in enumerate(sheet.iter_rows(values_only=True)):
            if index >= MAX_ROWS:
                break
            yield "\t".join("" if value is None else str(value) for value in row) + "\n"


def pptx_text(data: bytes) -> Iterator[str]:
    """The text frames of a presentation's first slides."""
    from pptx import Presentation  # noqa: PLC0415 — грузится только в дочернем процессе

    checked_zip(data)
    presentation = Presentation(io.BytesIO(data))
    for index, slide in enumerate(presentation.slides):
        if index >= MAX_SLIDES:
            break
        for shape in slide.shapes:
            if shape.has_text_frame:
                yield shape.text_frame.text + "\n"


def rtf_text(data: bytes) -> Iterator[str]:
    """An RTF document's text without its control words."""
    from striprtf.striprtf import rtf_to_text  # noqa: PLC0415 — грузится только в дочернем процессе

    yield rtf_to_text(data.decode("latin-1"), errors="replace")


def plain_text(data: bytes) -> Iterator[str]:
    """A text or data file as it is."""
    yield data.decode("utf-8", errors="replace")


READERS: Final[dict[DocumentFormat, Callable[[bytes], Iterator[str]]]] = {
    DocumentFormat.PDF: pdf_text,
    DocumentFormat.DOCX: docx_text,
    DocumentFormat.XLSX: xlsx_text,
    DocumentFormat.PPTX: pptx_text,
    DocumentFormat.RTF: rtf_text,
    DocumentFormat.TEXT: plain_text,
}
