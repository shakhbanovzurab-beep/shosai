"""A person's own notes on a meeting (plan §3.4 flow 7): what they typed, synced with the desktop.

Whoever may read a meeting keeps notes of their own on it: each reads and writes only their
own, and nobody else's are shown to anyone — the owner's to a member, a member's to the
owner — nor published by a share link. Before a person writes any, theirs are empty. A
write replaces the text — the last write wins — and the version grows by one in the same
statement, so two clients writing at once both count; the writing client is recorded. The
cabinet's route keeps the text to 50 000 characters, the native one to 256 KiB. The notes
are the writer's rows, written in their own scope. A meeting that is not kept (MT-D6)
stores none: 409 `private_meeting`.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from http import HTTPStatus
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.ids import new_id
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import Principal
from shosai.features.notes.application.visibility import meeting_for
from shosai.features.notes.domain.library import LibraryRuleError, NoteClient, checked_notes
from shosai.features.notes.domain.meetings import PRIVATE_MEETING
from shosai.features.notes.infrastructure.own_notes_records import OwnNotesRecord
from shosai.features.workspaces.contracts import ACCESS_POLICY


@dataclass(frozen=True, slots=True)
class OwnNotes:
    """A person's notes as last written."""

    text: str
    version: int
    client: NoteClient
    updated_at: datetime


def own_notes(record: OwnNotesRecord | None) -> OwnNotes | None:
    """The notes of a row, or None while the person has written none."""
    if record is None:
        return None
    return OwnNotes(record.markdown, record.version, NoteClient(record.client), record.updated_at)


class MyNotes:
    """Reads and writes a person's own notes on the meetings they may read."""

    def __init__(
        self,
        transactions: HomeTransactions,
        ports: PortDirectory,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._ports = ports
        self._clock = clock

    async def read(self, principal: Principal, meeting_id: UUID) -> OwnNotes | None:
        """The person's notes, None before any; 404 for a meeting they may not read."""
        policy = self._ports.get(ACCESS_POLICY)
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            meeting, _ = await meeting_for(session, policy, principal.user_id, meeting_id)
            record = await session.scalar(
                select(OwnNotesRecord).where(
                    OwnNotesRecord.session_id == meeting.id,
                    OwnNotesRecord.user_id == principal.user_id,
                )
            )
            return own_notes(record)

    async def write(
        self,
        principal: Principal,
        meeting_id: UUID,
        text: str,
        client: tuple[NoteClient, bool] = (NoteClient.WEB, False),
    ) -> OwnNotes:
        """Replace the person's notes from a client, natively or not; 422 over the cap."""
        writer, native = client
        try:
            markdown = checked_notes(text, native=native)
        except LibraryRuleError as error:
            raise AppError(error.code, HTTPStatus.UNPROCESSABLE_ENTITY) from error
        policy = self._ports.get(ACCESS_POLICY)
        now = self._clock()
        async with self._transactions.begin(principal.scope()) as session:
            meeting, _ = await meeting_for(session, policy, principal.user_id, meeting_id)
            if not meeting.kept:
                raise AppError(PRIVATE_MEETING, HTTPStatus.CONFLICT)
            mine = {"markdown": markdown, "client": writer.value, "updated_at": now}
            version = await session.scalar(
                insert(OwnNotesRecord)
                .values(
                    id=new_id(),
                    session_id=meeting.id,
                    user_id=principal.user_id,
                    version=1,
                    **mine,
                )
                .on_conflict_do_update(
                    index_elements=[OwnNotesRecord.session_id, OwnNotesRecord.user_id],
                    set_={**mine, "version": OwnNotesRecord.version + 1},
                )
                .returning(OwnNotesRecord.version)
            )
        return OwnNotes(markdown, int(version or 1), writer, now)
