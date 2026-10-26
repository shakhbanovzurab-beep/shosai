"""A question's attachments, read for its run (agent step 12b; Leo §7.4).

The run's first step reads the attachments the question names and has no note of yet: an image
goes to the model beside the question; a document's text is read by core's bounded reader — at
most 64 K characters a file and 256 K a question — kept whole for `core.read_result`, and its
beginning noted on the question, which every later turn reads again as the person's own file.
Each file is a step of the turn: one that cannot be read — rejected, broken, too large, gone —
fails alone with its code, and the model is told so. A regenerated question reads only its
images again; its documents' notes stay. The bytes stay in files' `transient/` prefix, which
the bucket expires after three days.
"""

import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any, Final

from pydantic import JsonValue
from sqlalchemy import select, update

from shosai.core.agent_tools.context import ToolContext
from shosai.core.ai.requests import MAX_IMAGE_BYTES, ImagePart
from shosai.core.db.transactions import HomeTransactions
from shosai.core.documents.extraction import DocumentReader, ExtractionError
from shosai.core.documents.formats import FileKind, sniff
from shosai.core.kernel.homes import Home
from shosai.core.storage.errors import ObjectNotFoundError, StorageUnavailableError
from shosai.core.storage.port import ObjectStorage
from shosai.features.agent.application.result_pages import ResultPages
from shosai.features.agent.application.run_work import RunWork, Step
from shosai.features.agent.application.turn_task import RunEmitter, TurnPayload
from shosai.features.agent.domain.attachments import (
    DIGEST_CHARS,
    FILE_CHARS,
    QUESTION_CHARS,
    Attached,
    attached_of,
    noted,
)
from shosai.features.agent.domain.runs import TURN_DEADLINE
from shosai.features.agent.domain.stream import Activity, EventKind
from shosai.features.agent.domain.threads import StepStatus
from shosai.features.agent.infrastructure.thread_records import AgentMessageRecord

MESSAGE = AgentMessageRecord
# Под этим именем текст вложения хранится для `core.read_result`.
ATTACHMENT_RESULT: Final = "core.attachment"
# Байт вложения не больше предела files; запас — на случай, если объект подменили.
READ_BYTES: Final = 10 * 1024**2
CHUNK: Final = 256 * 1024


class UnreadableAttachmentError(Exception):
    """The attachment cannot be read; `code` says why."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class AttachmentReader:
    """Reads a question's attachments for its run."""

    def __init__(
        self,
        transactions: HomeTransactions,
        storage: tuple[Mapping[Home, ObjectStorage], DocumentReader, ResultPages],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._objects, self._documents, self._pages = storage
        self._clock = clock

    async def read(
        self, payload: TurnPayload, work: RunWork, emitter: RunEmitter
    ) -> tuple[ImagePart, ...]:
        """The images the model sees beside the question; the documents noted on it."""
        async with self._transactions.begin(payload.scope(), read_only=True) as session:
            question = await session.scalar(
                select(MESSAGE).where(
                    MESSAGE.id == payload.question_id, MESSAGE.thread_id == payload.thread_id
                )
            )
        if question is None or not question.attachments:
            return ()
        known = {str(note.get("upload_id")): dict(note) for note in noted(question.digest)}
        images: list[ImagePart] = []
        notes: list[dict[str, JsonValue]] = []
        room = QUESTION_CHARS
        for attached in attached_of(question.attachments):
            earlier = known.get(attached.upload_id)
            if earlier is not None and earlier.get("kind") != "image":
                notes.append(earlier)
                continue
            note, image = await self._step(payload, work, emitter, (attached, room))
            chars = note.get("chars", 0)
            room -= chars if isinstance(chars, int) else 0
            notes.append(note)
            if image is not None:
                images.append(image)
        async with self._transactions.begin(payload.scope()) as session:
            await session.execute(
                update(MESSAGE)
                .where(MESSAGE.id == question.id, MESSAGE.created_at == question.created_at)
                .values(digest={"attachments": notes})
            )
        return tuple(images)

    async def _step(
        self, payload: TurnPayload, work: RunWork, emitter: RunEmitter, read: tuple[Attached, int]
    ) -> tuple[dict[str, JsonValue], ImagePart | None]:
        """One attachment as a step of the turn: its note, and its image if it is one."""
        attached, room = read
        seq = work.open_step()
        opened: dict[str, JsonValue] = {
            "id": f"step-{seq}", "seq": seq, "activity": Activity.READ_ATTACHMENT.value,
        }  # fmt: skip
        await emitter.emit(EventKind.STEP_STARTED, opened | {"detail": attached.name})
        began = time.monotonic()
        base: dict[str, JsonValue] = {"upload_id": attached.upload_id, "name": attached.name}
        code: str | None = None
        image: ImagePart | None = None
        try:
            found, image = await self._read(payload, attached, room)
            note = base | found
        except UnreadableAttachmentError as error:
            code = error.code
            note = base | {"kind": "unreadable", "code": code}
        status = StepStatus.DONE if code is None else StepStatus.FAILED
        took = int((time.monotonic() - began) * 1000)
        work.steps.append(
            Step(seq, Activity.READ_ATTACHMENT.value, attached.name, status.value, took, code)
        )
        closed = opened | {"duration_ms": took}
        if code is None:
            await emitter.emit(EventKind.STEP_COMPLETED, closed)
        else:
            await emitter.emit(EventKind.STEP_FAILED, closed | {"code": code})
        return note, image

    async def _read(
        self, payload: TurnPayload, attached: Attached, room: int
    ) -> tuple[dict[str, JsonValue], ImagePart | None]:
        """What the attachment is, read: an image, or a document's text kept and noted."""
        data = await self._bytes(payload.home, attached.key)
        sniffed = sniff(attached.name, data)
        if sniffed.kind is FileKind.IMAGE and sniffed.media_type is not None:
            if len(data) > MAX_IMAGE_BYTES:
                raise UnreadableAttachmentError("too_large")
            return {"kind": "image"}, ImagePart(data, sniffed.media_type)
        if sniffed.document is None:
            raise UnreadableAttachmentError("unsupported")
        if room <= 0:
            raise UnreadableAttachmentError("too_large")
        try:
            read = await self._documents.text(sniffed.document, data, min(FILE_CHARS, room))
        except ExtractionError as error:
            raise UnreadableAttachmentError(error.code) from error
        note: dict[str, JsonValue] = {
            "kind": "document", "text": read.text[:DIGEST_CHARS], "chars": len(read.text),
        }  # fmt: skip
        if read.truncated or len(read.text) > DIGEST_CHARS:
            context = ToolContext(payload.scope(), payload.run_id, self._clock() + TURN_DEADLINE)
            note["ref"] = str(await self._pages.keep(context, ATTACHMENT_RESULT, read.text))
        return note, None

    async def _bytes(self, home: Home, key: str) -> bytes:
        """The object's bytes, at most files' cap for an attachment."""
        chunks: list[bytes] = []
        size = 0
        try:
            async with self._objects[home].open(key) as stream:
                async for chunk in stream.chunks(CHUNK):
                    size += len(chunk)
                    if size > READ_BYTES:
                        raise UnreadableAttachmentError("too_large")
                    chunks.append(chunk)
        except ObjectNotFoundError as error:
            raise UnreadableAttachmentError("gone") from error
        except StorageUnavailableError as error:
            raise UnreadableAttachmentError("unavailable") from error
        return b"".join(chunks)


def listed_attachments(stored: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """A question's attachments as the history lists them."""
    return [attached.listed() for attached in attached_of(stored)]
