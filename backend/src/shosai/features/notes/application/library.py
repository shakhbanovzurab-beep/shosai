"""The cabinet's library and a meeting's page (plan step 7a): what a reader may see and change.

Every read starts from `visible_meetings` (inv-14) in the reader's own scope, so the
access policy decides inside the query and a meeting the reader may not read is a 404
like one that does not exist. The library is a keyset over the start and the id, newest
first; a page's cards are read in four more queries (`library_cards`). Whoever may manage
a meeting renames it; only its owner files their own personal meeting into one of their
folders (MT-D7). A reader who may only read is told so (403 `meeting_read_only`).
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Final
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.errors import AppError
from shosai.core.pagination.cursor import CursorCodec
from shosai.core.pagination.keyset import Keyset
from shosai.core.pagination.page import Page, PageRequest, page_of
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import Principal
from shosai.features.notes.application.library_cards import MeetingCard, cards_of
from shosai.features.notes.application.visibility import (
    meeting_for,
    meeting_scope,
    visible_meetings,
)
from shosai.features.notes.application.write_up_layout import layout_of
from shosai.features.notes.application.write_up_rewrites import TemplateNotFoundError
from shosai.features.notes.domain.meetings import checked_title
from shosai.features.notes.domain.reading import filing_refusal
from shosai.features.notes.domain.templates import builtin
from shosai.features.notes.infrastructure.meeting_records import (
    MEETING_RESOURCE,
    MeetingRecord,
    ParticipantRecord,
    SpeakerRecord,
)
from shosai.features.notes.infrastructure.notes_records import FolderRecord
from shosai.features.workspaces.contracts import ACCESS_POLICY, Viewer


class LibraryPosition(BaseModel):
    """Where a page of the library ended: the last meeting's start and id."""

    started_at: datetime
    meeting_id: UUID


LIBRARY_CURSOR: Final = CursorCodec("notes.library", LibraryPosition)
NOTES: Final = MEETING_RESOURCE.table
LIBRARY_ORDER: Final = Keyset((NOTES.c.started_at, NOTES.c.id), descending=True)
UNFILED: Final = "none"


class MeetingReadOnlyError(AppError):
    """The reader may read the meeting but not change it (403)."""

    def __init__(self) -> None:
        super().__init__("meeting_read_only", HTTPStatus.FORBIDDEN)


class FolderNotFoundError(AppError):
    """No such folder of the person's (404)."""

    def __init__(self) -> None:
        super().__init__("folder_not_found", HTTPStatus.NOT_FOUND)


@dataclass(frozen=True, slots=True)
class LibraryFilter:
    """The library's narrowing: a folder of the owner's, their meetings in none, a workspace."""

    folder: UUID | str | None = None
    workspace_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class MeetingChange:
    """A new title, folder or template; `*_given` tells "none" from "unchanged".

    A template is a shipped one's code or the id of the owner's own; None is Leo's layout.
    """

    title: str | None = None
    folder_id: UUID | None = None
    folder_given: bool = False
    template_id: str | None = None
    template_given: bool = False


@dataclass(frozen=True, slots=True)
class Participant:
    """A participant as the meeting's page shows them."""

    participant_id: UUID
    name: str | None
    email: str | None
    source: str


@dataclass(frozen=True, slots=True)
class Speaker:
    """A speaker of the meeting by number, their role and how long they spoke."""

    idx: int
    role: str
    talk_ms: int


@dataclass(frozen=True, slots=True)
class MeetingView:
    """A meeting's page: its card and what only the page shows."""

    card: MeetingCard
    manageable: bool
    template_id: str | None
    line_count: int
    revision: int
    run_id: UUID | None
    participants: tuple[Participant, ...]
    speakers: tuple[Speaker, ...]


class MeetingLibrary:
    """Lists, shows and changes the meetings a person may see."""

    def __init__(
        self,
        transactions: HomeTransactions,
        ports: PortDirectory,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._ports = ports
        self._clock = clock

    def _visible(self, principal: Principal, within: UUID | None = None) -> Select[MeetingRecord]:
        return visible_meetings(self._ports.get(ACCESS_POLICY), Viewer(principal.user_id, within))

    async def page(
        self, principal: Principal, request: PageRequest, narrowing: LibraryFilter
    ) -> Page[MeetingCard]:
        """A page of the meetings the person may see, newest first."""
        statement = self._visible(principal, narrowing.workspace_id)
        if narrowing.folder is not None:
            folder = None if narrowing.folder == UNFILED else narrowing.folder
            statement = statement.where(
                MeetingRecord.user_id == principal.user_id,
                MeetingRecord.org_id.is_(None),
                MeetingRecord.folder_id.is_(None)
                if folder is None
                else MeetingRecord.folder_id == folder,
            )
        after = None
        if request.cursor is not None:
            position = LIBRARY_CURSOR.decode(request.cursor)
            after = (position.started_at, position.meeting_id)
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            rows = (
                await session.scalars(LIBRARY_ORDER.page(statement, after, request.limit))
            ).all()
            cards = await cards_of(session, rows, principal.user_id)
        return page_of(
            cards, request, LIBRARY_CURSOR, lambda c: c,
            lambda c: LibraryPosition(started_at=c.started_at, meeting_id=c.meeting_id),
        )  # fmt: skip

    async def view(self, principal: Principal, meeting_id: UUID) -> MeetingView:
        """The meeting's page; `MeetingNotFoundError` for one the person may not read."""
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            return await self._view(session, principal, meeting_id)

    async def change(
        self, principal: Principal, meeting_id: UUID, change: MeetingChange
    ) -> MeetingView:
        """Rename the meeting or file it; its page after the change, in the meeting's scope."""
        policy = self._ports.get(ACCESS_POLICY)
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            scope = await meeting_scope(session, policy, principal.scope(), meeting_id)
        async with self._transactions.begin(scope) as session:
            meeting, manageable = await self._read(session, principal, meeting_id, lock=True)
            if not manageable:
                raise MeetingReadOnlyError
            if change.title is not None:
                meeting.title = checked_title(change.title)
            if change.folder_given:
                await self._file(session, principal, meeting, change.folder_id)
            if change.template_given:
                await self._choose(session, principal, meeting, change.template_id)
            meeting.updated_at = self._clock()
            await session.flush()
            return await self._view(session, principal, meeting_id)

    async def file_in(
        self, session: AsyncSession, principal: Principal, meeting_id: UUID, folder_id: UUID | None
    ) -> MeetingRecord:
        """File the person's own meeting, in the caller's transaction (Leo's write tool)."""
        meeting, manageable = await self._read(session, principal, meeting_id, lock=True)
        if not manageable:
            raise MeetingReadOnlyError
        await self._file(session, principal, meeting, folder_id)
        meeting.updated_at = self._clock()
        return meeting

    async def _file(
        self,
        session: AsyncSession,
        principal: Principal,
        meeting: MeetingRecord,
        folder_id: UUID | None,
    ) -> None:
        owner = meeting.user_id == principal.user_id
        refusal = filing_refusal(owner=owner, company=meeting.org_id is not None)
        if refusal is not None:
            raise AppError(refusal.value, HTTPStatus.CONFLICT)
        if folder_id is not None:
            folder = await session.get(FolderRecord, folder_id)
            if folder is None or folder.user_id != principal.user_id:
                raise FolderNotFoundError
        meeting.folder_id = folder_id

    async def _choose(
        self,
        session: AsyncSession,
        principal: Principal,
        meeting: MeetingRecord,
        template_id: str | None,
    ) -> None:
        """The template the meeting's next write-up uses.

        The write-up stage reads it in the owner's scope, so only the owner may choose their
        own template; another manager chooses a shipped one, or rewrites with theirs.
        """
        if template_id is not None and builtin(template_id) is None:
            if meeting.user_id != principal.user_id:
                raise AppError("template_not_shipped", HTTPStatus.CONFLICT)
            if await layout_of(session, template_id) is None:
                raise TemplateNotFoundError
        meeting.template_id = template_id

    async def _read(
        self, session: AsyncSession, principal: Principal, meeting_id: UUID, *, lock: bool = False
    ) -> tuple[MeetingRecord, bool]:
        policy = self._ports.get(ACCESS_POLICY)
        return await meeting_for(session, policy, principal.user_id, meeting_id, lock=lock)

    async def _view(
        self, session: AsyncSession, principal: Principal, meeting_id: UUID
    ) -> MeetingView:
        meeting, manageable = await self._read(session, principal, meeting_id)
        [card] = await cards_of(session, [meeting], principal.user_id)
        participants = await session.scalars(
            select(ParticipantRecord)
            .where(ParticipantRecord.session_id == meeting.id)
            .order_by(ParticipantRecord.created_at, ParticipantRecord.id)
        )
        speakers = await session.scalars(
            select(SpeakerRecord)
            .where(SpeakerRecord.session_id == meeting.id)
            .order_by(SpeakerRecord.idx)
        )
        return MeetingView(
            card=card, manageable=manageable, template_id=meeting.template_id,
            line_count=meeting.line_count, revision=meeting.notes_revision,
            run_id=meeting.latest_run_id,
            participants=tuple(
                Participant(p.id, p.name, p.email, p.source) for p in participants
            ),
            speakers=tuple(Speaker(s.idx, s.role, s.talk_ms) for s in speakers),
        )  # fmt: skip
