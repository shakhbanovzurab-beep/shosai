"""A readable meeting's content: transcript pages, the write-up, findings and map pages (§10).

Each read first finds the meeting through `visible_meetings`, in the reader's scope, so
content is never served for a meeting its reader may not read. The transcript is a keyset
over the offset and `seq` within the meeting's partition, up to 500 lines a page; the
findings are those the write-up lists (`findings_run_id`), by position; the map is the
stored tree's nodes in pre-order. The write-up inlines the findings each section lists, so
a page of notes reads in one request.
"""

from dataclasses import dataclass
from datetime import datetime
from http import HTTPStatus
from typing import Any, Final, cast
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import Table, select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.errors import AppError
from shosai.core.pagination.cursor import CursorCodec
from shosai.core.pagination.keyset import Keyset
from shosai.core.pagination.page import Page, PageRequest, page_of
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import Principal
from shosai.features.meetings.application.visibility import visible_meetings
from shosai.features.meetings.contracts import MeetingNotFoundError
from shosai.features.meetings.domain.findings import FindingKind
from shosai.features.meetings.domain.reading import MapRow, map_rows
from shosai.features.meetings.infrastructure.meeting_records import (
    MeetingRecord,
    TranscriptLineRecord,
)
from shosai.features.meetings.infrastructure.notes_records import FindingRecord, NotesRecord
from shosai.features.workspaces.contracts import ACCESS_POLICY, Viewer


class LinePosition(BaseModel):
    """Where a transcript page ended."""

    start_ms: int
    seq: int


class FindingPosition(BaseModel):
    """Where a page of findings ended."""

    position: int


class MapPosition(BaseModel):
    """Where a page of the map ended."""

    index: int = Field(ge=0)


TRANSCRIPT_CURSOR: Final = CursorCodec("meetings.transcript", LinePosition)
FINDINGS_CURSOR: Final = CursorCodec("meetings.findings", FindingPosition)
MAP_CURSOR: Final = CursorCodec("meetings.map", MapPosition)
LINES: Final = cast("Table", TranscriptLineRecord.__table__)
FINDINGS: Final = cast("Table", FindingRecord.__table__)
TRANSCRIPT_ORDER: Final = Keyset((LINES.c.start_ms, LINES.c.seq))
FINDINGS_ORDER: Final = Keyset((FINDINGS.c.position,))


class WriteUpNotFoundError(AppError):
    """The meeting has no write-up yet (404)."""

    def __init__(self) -> None:
        super().__init__("write_up_not_found", HTTPStatus.NOT_FOUND)


class MapNotFoundError(AppError):
    """The meeting has no map yet (404)."""

    def __init__(self) -> None:
        super().__init__("map_not_found", HTTPStatus.NOT_FOUND)


@dataclass(frozen=True, slots=True)
class WriteUp:
    """The write-up as stored and the findings its sections list, by id."""

    template_id: str
    automatic: bool
    written_at: datetime | None
    revision: int
    sections: list[dict[str, Any]]
    findings: dict[UUID, FindingRecord]


class MeetingContent:
    """Serves the content of meetings a person may read."""

    def __init__(self, transactions: HomeTransactions, ports: PortDirectory) -> None:
        self._transactions = transactions
        self._ports = ports

    async def _meeting(
        self, session: AsyncSession, principal: Principal, meeting_id: UUID
    ) -> MeetingRecord:
        policy = self._ports.get(ACCESS_POLICY)
        meeting = await session.scalar(
            visible_meetings(policy, Viewer(principal.user_id)).where(
                MeetingRecord.id == meeting_id
            )
        )
        if meeting is None:
            raise MeetingNotFoundError
        return meeting

    async def transcript(
        self, principal: Principal, meeting_id: UUID, request: PageRequest
    ) -> Page[TranscriptLineRecord]:
        """A page of the meeting's lines in the order they were spoken."""
        after = None
        if request.cursor is not None:
            position = TRANSCRIPT_CURSOR.decode(request.cursor)
            after = (position.start_ms, position.seq)
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            meeting = await self._meeting(session, principal, meeting_id)
            statement = select(TranscriptLineRecord).where(
                TranscriptLineRecord.session_id == meeting.id,
                TranscriptLineRecord.meeting_started_at == meeting.started_at,
            )
            rows = (
                await session.scalars(TRANSCRIPT_ORDER.page(statement, after, request.limit))
            ).all()
        return page_of(
            rows, request, TRANSCRIPT_CURSOR, lambda line: line,
            lambda line: LinePosition(start_ms=line.start_ms, seq=line.seq),
        )  # fmt: skip

    async def write_up(self, principal: Principal, meeting_id: UUID) -> WriteUp:
        """The write-up with the findings it lists; `WriteUpNotFoundError` before there is one."""
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            meeting = await self._meeting(session, principal, meeting_id)
            notes = await session.get(NotesRecord, meeting.id)
            if notes is None or notes.write_up is None or notes.write_up_template is None:
                raise WriteUpNotFoundError
            findings = await self._listed(session, meeting.id, notes.findings_run_id)
        return WriteUp(
            template_id=notes.write_up_template, automatic=notes.write_up_automatic,
            written_at=notes.write_up_written_at, revision=meeting.notes_revision,
            sections=list(notes.write_up.get("sections", [])),
            findings={finding.id: finding for finding in findings},
        )  # fmt: skip

    async def findings(
        self,
        principal: Principal,
        meeting_id: UUID,
        request: PageRequest,
        kind: FindingKind | None = None,
    ) -> Page[FindingRecord]:
        """A page of the findings the notes list, in the meeting's order."""
        after = None
        if request.cursor is not None:
            after = (FINDINGS_CURSOR.decode(request.cursor).position,)
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            meeting = await self._meeting(session, principal, meeting_id)
            notes = await session.get(NotesRecord, meeting.id)
            rows: list[FindingRecord] = []
            if notes is not None and notes.findings_run_id is not None:
                statement = select(FindingRecord).where(
                    FindingRecord.session_id == meeting.id,
                    FindingRecord.run_id == notes.findings_run_id,
                )
                if kind is not None:
                    statement = statement.where(FindingRecord.kind == kind.value)
                rows = list(
                    await session.scalars(FINDINGS_ORDER.page(statement, after, request.limit))
                )
        return page_of(
            rows, request, FINDINGS_CURSOR, lambda f: f,
            lambda f: FindingPosition(position=f.position),
        )  # fmt: skip

    async def map(
        self, principal: Principal, meeting_id: UUID, request: PageRequest
    ) -> Page[MapRow]:
        """A page of the map's nodes in pre-order; `MapNotFoundError` before there is a map."""
        start = 0 if request.cursor is None else MAP_CURSOR.decode(request.cursor).index + 1
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            meeting = await self._meeting(session, principal, meeting_id)
            notes = await session.get(NotesRecord, meeting.id)
        if notes is None or notes.map is None:
            raise MapNotFoundError
        rows = map_rows(notes.map)[start : start + request.limit + 1]
        return page_of(rows, request, MAP_CURSOR, lambda r: r, lambda r: MapPosition(index=r.index))

    async def _listed(
        self, session: AsyncSession, meeting_id: UUID, run_id: UUID | None
    ) -> list[FindingRecord]:
        if run_id is None:
            return []
        return list(
            await session.scalars(
                select(FindingRecord)
                .where(FindingRecord.session_id == meeting_id, FindingRecord.run_id == run_id)
                .order_by(FindingRecord.position)
            )
        )
