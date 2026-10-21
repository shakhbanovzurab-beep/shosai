"""The `meetings.meeting_reader` and `meetings.meeting_findings` bindings (step 15).

Workspaces' meeting shares (its step 8), knowledge, hubs, commitments and Leo's other
slices read meetings through these, in the caller's own transaction. Every call starts from
`visible_meetings` — the access policy, no deleted meeting, no meeting of an account in
identity's deletion window — and leaves out a meeting not kept (MT-D6), whose content was
never stored. A meeting the viewer may not read is absent from `facts` and `readable` and
`MeetingNotFoundError` for a transcript or findings, as one that does not exist. A batch of
facts takes three queries whatever its size; the transcript pages in the order the lines
were spoken, by the cursor of the cabinet's transcript.
"""

from collections import defaultdict
from collections.abc import Collection, Mapping, Sequence
from typing import Final
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.notes.application.library_cards import summary_of
from shosai.features.notes.application.live_transcript import stored_line
from shosai.features.notes.application.meeting_content import (
    TRANSCRIPT_CURSOR,
    TRANSCRIPT_ORDER,
    LinePosition,
)
from shosai.features.notes.application.visibility import visible_meetings
from shosai.features.notes.contracts import (
    FindingFacts,
    MeetingFacts,
    MeetingNotFoundError,
    ParticipantFacts,
    TranscriptPage,
)
from shosai.features.notes.domain.findings import FindingKind
from shosai.features.notes.domain.meetings import MeetingStatus
from shosai.features.notes.domain.transcript_archive import TranscriptLine, page_after
from shosai.features.notes.infrastructure.meeting_records import (
    MeetingRecord,
    ParticipantRecord,
    TranscriptLineRecord,
)
from shosai.features.notes.infrastructure.notes_records import FindingRecord, NotesRecord
from shosai.features.notes.infrastructure.transcript_archive import TranscriptArchive
from shosai.features.workspaces.contracts import ACCESS_POLICY, Viewer

LINES_PER_PAGE: Final = 500
Lines = TranscriptLineRecord


def readable_meetings(ports: PortDirectory, viewer: Viewer) -> Select[MeetingRecord]:
    """The meetings other slices may read for the viewer: visible and kept."""
    policy = ports.get(ACCESS_POLICY)
    return visible_meetings(policy, viewer).where(MeetingRecord.kept.is_(True))


async def readable_meeting(
    session: AsyncSession, ports: PortDirectory, viewer: Viewer, meeting_id: UUID
) -> MeetingRecord:
    """The meeting if the viewer may read it; `MeetingNotFoundError` otherwise."""
    meeting = await session.scalar(
        readable_meetings(ports, viewer).where(MeetingRecord.id == meeting_id)
    )
    if meeting is None:
        raise MeetingNotFoundError
    return meeting


class MeetingsReader:
    """Facts, transcript pages and a batch re-check of the meetings a viewer may read."""

    def __init__(
        self, transactions: HomeTransactions, ports: PortDirectory, archive: TranscriptArchive
    ) -> None:
        self._transactions = transactions
        self._ports = ports
        self._archive = archive

    async def facts(
        self, session: AsyncSession, viewer: Viewer, meeting_ids: Collection[UUID]
    ) -> Mapping[UUID, MeetingFacts]:
        """The readable ones among `meeting_ids`; the others are absent."""
        if not meeting_ids:
            return {}
        query = readable_meetings(self._ports, viewer).where(
            MeetingRecord.id.in_(list(meeting_ids))
        )
        meetings = list(await session.scalars(query))
        if not meetings:
            return {}
        ids = [meeting.id for meeting in meetings]
        people = await session.execute(
            select(ParticipantRecord.session_id, ParticipantRecord.name, ParticipantRecord.email)
            .where(ParticipantRecord.session_id.in_(ids))
            .order_by(ParticipantRecord.created_at, ParticipantRecord.id)
        )
        listed: dict[UUID, list[ParticipantFacts]] = defaultdict(list)
        for meeting_id, name, email in people:
            listed[meeting_id].append(ParticipantFacts(name, email))
        notes = await session.execute(
            select(NotesRecord.session_id, NotesRecord.write_up).where(
                NotesRecord.session_id.in_(ids)
            )
        )
        summaries = {meeting_id: summary_of(write_up) for meeting_id, write_up in notes}
        return {
            meeting.id: MeetingFacts(
                meeting_id=meeting.id, user_id=meeting.user_id, org_id=meeting.org_id,
                title=meeting.title, status=MeetingStatus(meeting.status),
                started_at=meeting.started_at, ended_at=meeting.ended_at,
                seconds=meeting.seconds, participants=tuple(listed[meeting.id]),
                summary=summaries.get(meeting.id),
            )
            for meeting in meetings
        }  # fmt: skip

    async def transcript(
        self,
        home: Home,
        viewer: Viewer,
        meeting_id: UUID,
        cursor: str | None,
        limit: int,
    ) -> TranscriptPage:
        """A page of a readable meeting's lines as spoken; `MeetingNotFoundError` otherwise.

        It opens its own transaction: an archived transcript is read from the bucket after it,
        never inside one (§14 rule 8). A cursor that is not this transcript's is
        `invalid_cursor`.
        """
        if not 1 <= limit <= LINES_PER_PAGE:
            message = f"страница расшифровки — от 1 до {LINES_PER_PAGE} строк"
            raise ValueError(message)
        after = None
        if cursor is not None:
            position = TRANSCRIPT_CURSOR.decode(cursor)
            after = (position.start_ms, position.seq)
        rows: Sequence[TranscriptLine] = ()
        scope = TenancyScope(home, viewer.user_id)
        async with self._transactions.begin(scope, read_only=True) as session:
            meeting = await readable_meeting(session, self._ports, viewer, meeting_id)
            archived = meeting.transcript_archive_key
            if archived is None:
                statement = select(Lines).where(
                    Lines.session_id == meeting.id, Lines.meeting_started_at == meeting.started_at
                )
                rows = list(await session.scalars(TRANSCRIPT_ORDER.page(statement, after, limit)))
        if archived is not None:
            rows = page_after(await self._archive.lines(home, archived), after, limit)
        shown = rows[:limit]
        following = None
        if len(rows) > limit:
            last = shown[-1]
            following = TRANSCRIPT_CURSOR.encode(LinePosition(start_ms=last.start_ms, seq=last.seq))
        return TranscriptPage(tuple(stored_line(row) for row in shown), following)

    async def readable(
        self, session: AsyncSession, viewer: Viewer, meeting_ids: Collection[UUID]
    ) -> frozenset[UUID]:
        """The readable ones among `meeting_ids`, in one query (search hits, Leo)."""
        if not meeting_ids:
            return frozenset()
        query = (
            readable_meetings(self._ports, viewer)
            .with_only_columns(MeetingRecord.id)
            .where(MeetingRecord.id.in_(list(meeting_ids)))
        )
        return frozenset(await session.scalars(query))


class MeetingsFindings:
    """The findings of the current notes of a meeting the viewer may read."""

    def __init__(self, ports: PortDirectory) -> None:
        self._ports = ports

    async def of(
        self, session: AsyncSession, viewer: Viewer, meeting_id: UUID
    ) -> Sequence[FindingFacts]:
        """In the meeting's order; `MeetingNotFoundError` for a meeting the viewer cannot read."""
        meeting = await readable_meeting(session, self._ports, viewer, meeting_id)
        run = await session.scalar(
            select(NotesRecord.findings_run_id).where(NotesRecord.session_id == meeting.id)
        )
        if run is None:
            return ()
        records = await session.scalars(
            select(FindingRecord)
            .where(FindingRecord.session_id == meeting.id, FindingRecord.run_id == run)
            .order_by(FindingRecord.position)
        )
        return tuple(
            FindingFacts(
                finding_id=r.id, kind=FindingKind(r.kind), text=r.text, topic=r.topic,
                owner_name=r.owner_name, due_on=r.due_on, start_ms=r.start_ms,
                end_ms=r.end_ms, quote=r.quote,
            )
            for r in records
        )  # fmt: skip
