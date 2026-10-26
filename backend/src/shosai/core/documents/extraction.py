"""A document's text, read off the event loop in a bounded child process.

Each read starts `python -I -m shosai.core.documents.child` with an empty environment — no
setting, no secret — and hands it the bytes; the child caps its own memory and CPU before any
parser loads. The parent waits at most its timeout and kills a child that runs over; a few
reads run at once per process, the rest wait their turn. A read that fails says why by a code:
`malformed`, `encrypted`, `too_large`, `timeout` or `failed`. Leo reads attachments with it, and
knowledge will index the same formats with it.
"""

import asyncio
import json
import os
import sys
from dataclasses import dataclass
from datetime import timedelta
from typing import Final

import structlog

from shosai.core.documents.formats import DocumentFormat

CHILD: Final = "shosai.core.documents.child"
CLEAN_ENVIRONMENT: Final = {"LANG": "C.UTF-8", "PATH": os.defpath}
log = structlog.stdlib.get_logger(__name__)


class ExtractionError(Exception):
    """The document's text could not be read; `code` says why."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class ExtractedText:
    """A document's text and whether it was cut at the limit."""

    text: str
    truncated: bool


class DocumentReader:
    """Reads documents' text in bounded child processes, a few at once."""

    def __init__(self, at_once: int = 2, timeout: timedelta = timedelta(seconds=30)) -> None:
        self._gate = asyncio.Semaphore(at_once)
        self._timeout = timeout

    async def text(self, document: DocumentFormat, data: bytes, limit: int) -> ExtractedText:
        """The document's text up to `limit` characters; `ExtractionError` when unreadable."""
        async with self._gate:
            child = await asyncio.create_subprocess_exec(
                sys.executable, "-I", "-m", CHILD, document.value, str(limit),
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE, env=CLEAN_ENVIRONMENT,
            )  # fmt: skip
            try:
                async with asyncio.timeout(self._timeout.total_seconds()):
                    out, err = await child.communicate(data)
            except TimeoutError as error:
                child.kill()
                await child.wait()
                raise ExtractionError("timeout") from error
        return answer_of(out, err, child.returncode)


def answer_of(out: bytes, err: bytes, code: int | None) -> ExtractedText:
    """The child's one line as text, or the error it ended with."""
    try:
        answer = json.loads(out)
    except ValueError:
        answer = None
    if not isinstance(answer, dict):
        # Процесс убит пределом (память, CPU) или упал: причина — только в коде и stderr.
        log.warning(
            "Разбор документа оборвался",
            returncode=code, stderr=err.decode("utf-8", errors="replace")[-200:],
        )  # fmt: skip
        raise ExtractionError("failed")
    if "error" in answer:
        raise ExtractionError(str(answer["error"]))
    return ExtractedText(str(answer.get("text", "")), bool(answer.get("truncated", False)))
