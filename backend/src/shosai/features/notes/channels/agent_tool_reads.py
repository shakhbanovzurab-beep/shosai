"""The read tools of Leo's `meetings` toolset: search, digest, transcript, findings (step 14).

Each acts for the person of the tool context's scope, never for an id the model names, and
sees exactly what `visible_meetings` admits: a meeting they may not read is `not_found`, like
one that does not exist. Each names the meetings it read as the sources of Leo's answer, in
their workspace (`agent_tool_sources`). A transcript page holds the lines that fit the tool's
token budget (`agent_transcript_pages`) and names where the next page starts.
"""

from collections.abc import Sequence
from datetime import UTC, datetime, time, timedelta
from typing import Final
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.agent_tools.bindings import ReadTool
from shosai.core.agent_tools.context import ToolContext
from shosai.core.agent_tools.results import ToolErrorCode, ToolResult
from shosai.core.db.transactions import HomeTransactions
from shosai.core.ports.directory import PortDirectory
from shosai.features.notes.application.library_cards import cards_of
from shosai.features.notes.application.visibility import visible_meetings
from shosai.features.notes.channels.agent_tool_sources import (
    LINE_QUOTE,
    meeting_source,
    meeting_spaces,
    moment,
)
from shosai.features.notes.channels.agent_tools import (
    GET,
    LIST_FINDINGS,
    READ_TRANSCRIPT,
    SEARCH,
    FindingCounts,
    FoundMeeting,
    FoundMeetings,
    ListFindings,
    MeetingDigest,
    MeetingFinding,
    MeetingFindings,
    MeetingId,
    Participant,
    ReadTranscript,
    SearchMeetings,
    TranscriptPage,
)
from shosai.features.notes.channels.agent_transcript_pages import LINES_READ, owner_voice, page_of
from shosai.features.notes.domain.findings import FindingKind
from shosai.features.notes.domain.transcript_archive import TranscriptLine, spoken_order
from shosai.features.notes.infrastructure.meeting_records import (
    MeetingRecord,
    ParticipantRecord,
    SpeakerRecord,
    TranscriptLineRecord,
)
from shosai.features.notes.infrastructure.notes_records import FindingRecord, NotesRecord
from shosai.features.notes.infrastructure.transcript_archive import TranscriptArchive
from shosai.features.workspaces.contracts import ACCESS_POLICY, Viewer

SUMMARY_CHARS: Final = 300
PARTICIPANTS_SHOWN: Final = 50
FINDINGS_SHOWN: Final = 200
Lines = TranscriptLineRecord


def clipped(text: str | None, limit: int) -> str | None:
    """The text within the limit, an ellipsis where it was cut."""
    if text is None or len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


class MeetingReads:
    """The four read tools over the meetings the person may read."""

    def __init__(
        self, transactions: HomeTransactions, ports: PortDirectory, archive: TranscriptArchive
    ) -> None:
        self._transactions = transactions
        self._ports = ports
        self._archive = archive

    def bound(
        self,
    ) -> tuple[
        ReadTool[SearchMeetings, FoundMeetings],
        ReadTool[MeetingId, MeetingDigest],
        ReadTool[ReadTranscript, TranscriptPage],
        ReadTool[ListFindings, MeetingFindings],
    ]:
        """The four read tools."""
        return (
            ReadTool(SEARCH, self.search),
            ReadTool(GET, self.get),
            ReadTool(READ_TRANSCRIPT, self.read_transcript),
            ReadTool(LIST_FINDINGS, self.list_findings),
        )

    async def search(
        self, arguments: SearchMeetings, context: ToolContext
    ) -> ToolResult[FoundMeetings]:
        """Meetings matching the title and days, newest first."""
        user_id = meeting_viewer(context)
        statement = visible_meetings(self._ports.get(ACCESS_POLICY), Viewer(user_id))
        if arguments.query is not None:
            statement = statement.where(
                MeetingRecord.title.icontains(arguments.query, autoescape=True)
            )
        if arguments.started_from is not None:
            start = datetime.combine(arguments.started_from, time.min, UTC)
            statement = statement.where(MeetingRecord.started_at >= start)
        if arguments.started_to is not None:
            end = datetime.combine(arguments.started_to, time.min, UTC) + timedelta(days=1)
            statement = statement.where(MeetingRecord.started_at < end)
        statement = statement.order_by(
            MeetingRecord.started_at.desc(), MeetingRecord.id.desc()
        ).limit(arguments.limit + 1)
        async with self._transactions.begin(context.scope, read_only=True) as session:
            found = list(await session.scalars(statement))
            cards = await cards_of(session, found[: arguments.limit], user_id)
            policy = self._ports.get(ACCESS_POLICY)
            spaces = await meeting_spaces(session, policy, user_id, found[: arguments.limit])
        meetings = [
            FoundMeeting(
                meeting_id=c.meeting_id, title=c.title, started_at=c.started_at,
                seconds=c.seconds, owned=c.owned, summary=clipped(c.summary, SUMMARY_CHARS),
            )
            for c in cards
        ]  # fmt: skip
        sources = tuple(
            meeting_source((c.meeting_id, c.title, spaces[c.meeting_id])) for c in cards
        )
        more = len(found) > arguments.limit
        return ToolResult(FoundMeetings(meetings=meetings, more=more), sources=sources)

    async def get(self, arguments: MeetingId, context: ToolContext) -> ToolResult[MeetingDigest]:
        """A readable meeting's facts and Leo's summary."""
        async with self._transactions.begin(context.scope, read_only=True) as session:
            meeting = await self._visible(session, context, arguments.meeting_id)
            if meeting is None:
                return ToolResult.failed(ToolErrorCode.NOT_FOUND)
            [card] = await cards_of(session, [meeting], meeting_viewer(context))
            people = await session.scalars(
                select(ParticipantRecord)
                .where(ParticipantRecord.session_id == meeting.id)
                .order_by(ParticipantRecord.created_at, ParticipantRecord.id)
                .limit(PARTICIPANTS_SHOWN)
            )
            counts = await self._counts(session, meeting.id)
            participants = [Participant(name=p.name, email=p.email) for p in people]
            space = await self._space(session, context, meeting)
        source = meeting_source((meeting.id, meeting.title, space), quote=card.summary or "")
        return ToolResult(
            sources=(source,),
            output=MeetingDigest(
                meeting_id=meeting.id, title=meeting.title, status=meeting.status,
                started_at=meeting.started_at, ended_at=meeting.ended_at,
                seconds=meeting.seconds, owned=card.owned, participants=participants,
                notes=card.notes, summary=card.summary, findings=counts,
                transcript_lines=meeting.line_count,
            )
        )  # fmt: skip

    async def read_transcript(
        self, arguments: ReadTranscript, context: ToolContext
    ) -> ToolResult[TranscriptPage]:
        """The lines from a moment on that fit the budget, and where the next page starts."""
        async with self._transactions.begin(context.scope, read_only=True) as session:
            meeting = await self._visible(session, context, arguments.meeting_id)
            if meeting is None:
                return ToolResult.failed(ToolErrorCode.NOT_FOUND)
            archived = meeting.transcript_archive_key
            lines: Sequence[TranscriptLine] = ()
            if archived is None:
                lines = list(
                    await session.scalars(
                        select(Lines)
                        .where(
                            Lines.session_id == meeting.id,
                            Lines.meeting_started_at == meeting.started_at,
                            Lines.start_ms >= arguments.from_ms,
                        )
                        .order_by(Lines.start_ms, Lines.seq)
                        .limit(LINES_READ + 1)
                    )
                )
            roles = await session.execute(
                select(SpeakerRecord.idx, SpeakerRecord.role).where(
                    SpeakerRecord.session_id == meeting.id
                )
            )
            owner = owner_voice({idx: role for idx, role in roles})
            space = await self._space(session, context, meeting)
        if archived is not None:
            spoken = spoken_order(await self._archive.lines(context.scope.home, archived))
            lines = [line for line in spoken if line.start_ms >= arguments.from_ms][
                : LINES_READ + 1
            ]
        page = page_of(lines, owner)
        first = page.lines[0] if page.lines else None
        source = meeting_source(
            (meeting.id, meeting.title, space),
            locator=None if first is None else moment(first.at_ms),
            quote="" if first is None else first.text[:LINE_QUOTE],
        )
        return ToolResult(page, sources=(source,))

    async def list_findings(
        self, arguments: ListFindings, context: ToolContext
    ) -> ToolResult[MeetingFindings]:
        """The findings of the meeting's current notes, in the meeting's order."""
        async with self._transactions.begin(context.scope, read_only=True) as session:
            meeting = await self._visible(session, context, arguments.meeting_id)
            if meeting is None:
                return ToolResult.failed(ToolErrorCode.NOT_FOUND)
            run = await session.scalar(
                select(NotesRecord.findings_run_id).where(NotesRecord.session_id == meeting.id)
            )
            statement = select(FindingRecord).where(
                FindingRecord.session_id == meeting.id, FindingRecord.run_id == run
            )
            if arguments.kind is not None:
                statement = statement.where(FindingRecord.kind == arguments.kind.value)
            records = await session.scalars(
                statement.order_by(FindingRecord.position).limit(FINDINGS_SHOWN)
            )
            findings = [
                MeetingFinding(
                    finding_id=r.id, kind=FindingKind(r.kind), text=r.text,
                    owner_name=r.owner_name, due_on=r.due_on, at_ms=r.start_ms, quote=r.quote,
                )
                for r in records
            ]  # fmt: skip
            space = await self._space(session, context, meeting)
        source = meeting_source((meeting.id, meeting.title, space))
        return ToolResult(MeetingFindings(findings=findings), sources=(source,))

    async def _visible(
        self, session: AsyncSession, context: ToolContext, meeting_id: UUID
    ) -> MeetingRecord | None:
        statement = visible_meetings(
            self._ports.get(ACCESS_POLICY), Viewer(meeting_viewer(context))
        )
        meeting: MeetingRecord | None = await session.scalar(
            statement.where(MeetingRecord.id == meeting_id)
        )
        return meeting

    async def _space(
        self, session: AsyncSession, context: ToolContext, meeting: MeetingRecord
    ) -> UUID | None:
        """The meeting's space as Leo names its source."""
        policy, viewer = self._ports.get(ACCESS_POLICY), meeting_viewer(context)
        return (await meeting_spaces(session, policy, viewer, [meeting]))[meeting.id]

    async def _counts(self, session: AsyncSession, meeting_id: UUID) -> FindingCounts:
        run = await session.scalar(
            select(NotesRecord.findings_run_id).where(NotesRecord.session_id == meeting_id)
        )
        rows = await session.execute(
            select(FindingRecord.kind, func.count())
            .where(FindingRecord.session_id == meeting_id, FindingRecord.run_id == run)
            .group_by(FindingRecord.kind)
        )
        counts = {kind: int(count) for kind, count in rows}
        return FindingCounts(
            key_points=counts.get(FindingKind.KEY_POINT.value, 0),
            decisions=counts.get(FindingKind.DECISION.value, 0),
            action_items=counts.get(FindingKind.ACTION_ITEM.value, 0),
            promises=counts.get(FindingKind.PROMISE.value, 0),
            risks=counts.get(FindingKind.RISK.value, 0),
            questions=counts.get(FindingKind.QUESTION.value, 0),
        )


def meeting_viewer(context: ToolContext) -> UUID:
    """The person the call acts for; a tool context always has one."""
    user_id = context.scope.user_id
    if user_id is None:
        message = "инструмент встреч вызывается только от имени человека"
        raise ValueError(message)
    return user_id
