"""The native library (plan step 12, MT-D1, MT-D12): what the shipped clients read and write.

`GET /v1/me/sessions` lists the person's own meetings, newest first, narrowed by an exact
status and a search in the title, and only the newest 200 that match — an `offset` past
them answers nothing, so no offset reads deep. `full` reads a meeting the person may read
with all its lines, its speakers and its map; the note reads the person's own notes (empty
before they write any), Leo's write-up with the findings it lists, and where each line
starts. The person's language and name word what the clients show.
"""

from dataclasses import dataclass
from typing import Any, Final
from uuid import UUID

from sqlalchemy import select

from shosai.core.db.transactions import HomeTransactions
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import ACCOUNT_PROFILE_READER, AccountProfile, Principal
from shosai.features.notes.application.stored_findings import findings_of
from shosai.features.notes.application.visibility import meeting_for
from shosai.features.notes.domain.findings import Finding
from shosai.features.notes.domain.reading import map_rows
from shosai.features.notes.infrastructure.meeting_records import (
    MeetingRecord,
    SpeakerRecord,
    TranscriptLineRecord,
)
from shosai.features.notes.infrastructure.notes_records import NotesRecord
from shosai.features.notes.infrastructure.own_notes_records import OwnNotesRecord
from shosai.features.workspaces.contracts import ACCESS_POLICY

NEWEST: Final = 200
Lines = TranscriptLineRecord


@dataclass(frozen=True, slots=True)
class NativeRow:
    """A meeting of the list and how many nodes its map has."""

    meeting: MeetingRecord
    map_nodes: int


@dataclass(frozen=True, slots=True)
class NativeMeeting:
    """A meeting with its lines, the roles of its speakers, its map and its reader."""

    meeting: MeetingRecord
    lines: list[TranscriptLineRecord]
    roles: dict[int, str]
    map: dict[str, Any] | None
    reader: AccountProfile | None


@dataclass(frozen=True, slots=True)
class NativeNote:
    """The person's notes on a meeting, Leo's write-up and its findings, and line starts."""

    meeting: MeetingRecord
    own: OwnNotesRecord | None
    notes: NotesRecord | None
    findings: dict[UUID, Finding]
    starts: list[tuple[int, int]]
    language: str | None


def searched(text: str) -> str:
    """A `LIKE` pattern finding the text anywhere, its wildcards taken literally."""
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


class NativeLibrary:
    """Reads the person's meetings for the shipped clients."""

    def __init__(self, transactions: HomeTransactions, ports: PortDirectory) -> None:
        self._transactions = transactions
        self._ports = ports

    async def rows(
        self, principal: Principal, filters: tuple[str | None, str | None], page: tuple[int, int]
    ) -> list[NativeRow]:
        """A page of the person's newest 200 meetings matching the filters."""
        (status, text), (limit, offset) = filters, page
        size = min(limit, NEWEST - offset)
        if size <= 0:
            return []
        statement = select(MeetingRecord).where(
            MeetingRecord.user_id == principal.user_id, MeetingRecord.deleted_at.is_(None)
        )
        if status:
            statement = statement.where(MeetingRecord.status == status)
        if text:
            statement = statement.where(MeetingRecord.title.ilike(searched(text), escape="\\"))
        statement = (
            statement.order_by(MeetingRecord.started_at.desc(), MeetingRecord.id.desc())
            .offset(offset)
            .limit(size)
        )
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            meetings = list((await session.scalars(statement)).all())
            maps = await session.execute(
                select(NotesRecord.session_id, NotesRecord.map).where(
                    NotesRecord.session_id.in_([m.id for m in meetings])
                )
            )
            nodes = {meeting_id: len(map_rows(tree)) if tree else 0 for meeting_id, tree in maps}
        return [NativeRow(meeting, nodes.get(meeting.id, 0)) for meeting in meetings]

    async def full(self, principal: Principal, meeting_id: UUID) -> NativeMeeting:
        """A meeting the person may read, with every line; `meeting_not_found` otherwise."""
        policy = self._ports.get(ACCESS_POLICY)
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            meeting, _ = await meeting_for(session, policy, principal.user_id, meeting_id)
            lines = await session.scalars(
                select(Lines)
                .where(
                    Lines.session_id == meeting.id, Lines.meeting_started_at == meeting.started_at
                )
                .order_by(Lines.start_ms, Lines.seq)
            )
            roles = await session.execute(
                select(SpeakerRecord.idx, SpeakerRecord.role).where(
                    SpeakerRecord.session_id == meeting.id
                )
            )
            tree = await session.scalar(
                select(NotesRecord.map).where(NotesRecord.session_id == meeting.id)
            )
            reader = await self._ports.get(ACCOUNT_PROFILE_READER).profile(
                session, principal.user_id
            )
            return NativeMeeting(
                meeting, list(lines.all()), {idx: role for idx, role in roles}, tree, reader
            )

    async def note(self, principal: Principal, meeting_id: UUID) -> NativeNote:
        """The person's own notes and Leo's write-up of a meeting they may read."""
        policy = self._ports.get(ACCESS_POLICY)
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            meeting, _ = await meeting_for(session, policy, principal.user_id, meeting_id)
            own = await session.scalar(
                select(OwnNotesRecord).where(
                    OwnNotesRecord.session_id == meeting.id,
                    OwnNotesRecord.user_id == principal.user_id,
                )
            )
            notes = await session.get(NotesRecord, meeting.id)
            run = notes.findings_run_id if notes is not None else None
            findings = dict(await findings_of(session, meeting.id, run))
            starts = await session.execute(
                select(Lines.seq, Lines.start_ms)
                .where(
                    Lines.session_id == meeting.id, Lines.meeting_started_at == meeting.started_at
                )
                .order_by(Lines.start_ms, Lines.seq)
            )
            reader = await self._ports.get(ACCOUNT_PROFILE_READER).profile(
                session, principal.user_id
            )
            language = reader.language if reader is not None else None
            return NativeNote(
                meeting, own, notes, findings, [(seq, start) for seq, start in starts], language
            )
