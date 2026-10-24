"""The thing on the person's page, told to Leo through its owner (Leo §7.3 segment 7, step 5b).

The cabinet names the page and, when there is one, the meeting, task, board or file it shows.
Its owner's reader tells what the person may read of it — a meeting nobody shares with them,
a deleted task, another person's file are simply not mentioned. Words the person did not
write — a meeting's title and summary, a colleague's task, a file's name — enter wrapped and
labelled; the person's own task and board do not need it. A digest stays within 1 500 tokens.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Final
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.agent_tools.spec import Provenance
from shosai.core.ports.directory import PortDirectory
from shosai.features.agent.domain.context import clip
from shosai.features.agent.domain.wrapper import Label, wrap
from shosai.features.files.contracts import FILE_READER
from shosai.features.notes.contracts import MEETING_READER
from shosai.features.tasks.contracts import BOARD_READER, TASK_READER
from shosai.features.workspaces.contracts import Viewer

DIGEST_TOKENS: Final = 1_500
# Строки дайджеста, которые читает модель: английские, зарегистрированы в тесте model-facing.
MEETING: Final = "The page shows a meeting from {moment} UTC, {status}:"
TASK: Final = "The page shows a task, {status}{due}:"
DUE: Final = ", due {day}"
BOARD: Final = "The page shows the person's board:"
FILE: Final = "The page shows a file ({kind}, {size} bytes):"
SUBJECT_TEXTS: Final = (MEETING, TASK, DUE, BOARD, FILE)


class SubjectKind(StrEnum):
    """What a cabinet page can show to Leo."""

    MEETING = "meeting"
    TASK = "task"
    BOARD = "board"
    FILE = "file"


@dataclass(frozen=True, slots=True)
class Subject:
    """The thing a page shows: its kind and id."""

    kind: SubjectKind
    subject_id: UUID


@dataclass(frozen=True, slots=True)
class Digest:
    """What Leo is told of the subject, and whether its words came from someone else."""

    text: str
    external: bool


type Reader = tuple[AsyncSession, PortDirectory, UUID, str]


async def subject_digest(
    session: AsyncSession,
    ports: PortDirectory,
    reader: tuple[UUID, Subject],
    boundary: str,
) -> Digest | None:
    """The subject as the person may read it, or None when they may not or it is gone."""
    user_id, subject = reader
    digest = DIGESTS[subject.kind]
    return await digest((session, ports, user_id, boundary), subject.subject_id)


async def meeting_digest(reader: Reader, key: UUID) -> Digest | None:
    """A meeting's time, status, title and summary: its speech, wrapped."""
    session, ports, user_id, boundary = reader
    meeting = (await ports.get(MEETING_READER).facts(session, Viewer(user_id), [key])).get(key)
    if meeting is None:
        return None
    head = MEETING.format(
        moment=meeting.started_at.strftime("%Y-%m-%d %H:%M"), status=meeting.status.value
    )
    body = "\n".join(part for part in (meeting.title, meeting.summary or "") if part)
    return external(head, body, Provenance.MEETING_SPEECH, boundary)


async def task_digest(reader: Reader, key: UUID) -> Digest | None:
    """A task's status, day and title; a colleague's title wrapped, the person's own not."""
    session, ports, user_id, boundary = reader
    task = (await ports.get(TASK_READER).facts(session, Viewer(user_id), [key])).get(key)
    if task is None:
        return None
    due = DUE.format(day=task.due_on.isoformat()) if task.due_on else ""
    head = TASK.format(status=task.status.value, due=due)
    if task.user_id == user_id:
        return Digest(f"{head}\n{clip(task.title, DIGEST_TOKENS)}", external=False)
    return external(head, task.title, Provenance.TASK_FOREIGN, boundary)


async def board_digest(reader: Reader, key: UUID) -> Digest | None:
    """The person's own board, by its name."""
    session, ports, user_id, _ = reader
    boards = await ports.get(BOARD_READER).boards(session, user_id)
    board = next((found for found in boards if found.board_id == key), None)
    if board is None:
        return None
    return Digest(f"{BOARD}\n{clip(board.name, DIGEST_TOKENS)}", external=False)


async def file_digest(reader: Reader, key: UUID) -> Digest | None:
    """A file's kind, size and name, the name wrapped."""
    session, ports, user_id, boundary = reader
    file = (await ports.get(FILE_READER).facts(session, Viewer(user_id), [key])).get(key)
    if file is None:
        return None
    head = FILE.format(kind=file.kind.value, size=file.size_bytes)
    return external(head, file.name, Provenance.FILE_FOREIGN, boundary)


DIGESTS: Final[dict[SubjectKind, Callable[[Reader, UUID], Awaitable[Digest | None]]]] = {
    SubjectKind.MEETING: meeting_digest,
    SubjectKind.TASK: task_digest,
    SubjectKind.BOARD: board_digest,
    SubjectKind.FILE: file_digest,
}


def external(head: str, body: str, provenance: Provenance, boundary: str) -> Digest:
    """A digest whose words someone else wrote: wrapped, labelled, within its budget."""
    wrapped = wrap(clip(body, DIGEST_TOKENS), Label.of(provenance), boundary)
    return Digest(f"{head}\n{wrapped}", external=True)
