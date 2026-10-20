"""A meeting's page through its share link, and the link's comments (step 13, MT-D5, MT-D12).

The page is read in the meeting owner's scope once the link resolves (`shared_links.py`):
the write-up with the findings it lists, the participants, and — when the link shows it —
the transcript, its first 3 000 lines. It never carries an address, anyone's own notes or
the audio; the redaction of names happens where the page is shaped. Comments are the
newest 200, oldest first; a link that does not allow them answers 409 `comments_closed`.
A comment is written in the owner's scope, with no reader's id or address kept.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Final
from uuid import UUID

from sqlalchemy import select

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.ids import new_id
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import ACCOUNT_PROFILE_READER
from shosai.features.meetings.application.shared_links import SharedLinks
from shosai.features.meetings.application.stored_findings import findings_of
from shosai.features.meetings.domain.findings import Finding
from shosai.features.meetings.domain.redaction import Person
from shosai.features.meetings.domain.sharing import (
    COMMENTS_SHOWN,
    CommentRuleError,
    checked_comment,
)
from shosai.features.meetings.infrastructure.meeting_records import (
    MeetingRecord,
    ParticipantRecord,
    SpeakerRecord,
    TranscriptLineRecord,
)
from shosai.features.meetings.infrastructure.notes_records import NotesRecord
from shosai.features.meetings.infrastructure.share_records import (
    ShareCommentRecord,
    ShareLinkRecord,
)

LINES_SHOWN: Final = 3000
Lines = TranscriptLineRecord


@dataclass(frozen=True, slots=True)
class SharedPage:
    """What a link's page is made of, before the link's redaction."""

    link: ShareLinkRecord
    meeting: MeetingRecord
    participants: list[Person]
    notes: NotesRecord | None
    findings: dict[UUID, Finding]
    lines: list[TranscriptLineRecord] | None
    truncated: bool
    roles: dict[int, str]
    owner_name: str | None


class CommentsClosedError(AppError):
    """The link does not take comments (409)."""

    def __init__(self) -> None:
        super().__init__("comments_closed", HTTPStatus.CONFLICT)


class SharedPages:
    """Serves the pages and comments of share links."""

    def __init__(
        self,
        transactions: HomeTransactions,
        collaborators: tuple[SharedLinks, PortDirectory],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._links, self._ports = collaborators
        self._clock = clock

    async def page(self, token: str) -> SharedPage:
        """The link's page; `share_not_found` for any link that does not open."""
        scope, meeting_id = await self._links.located(token)
        async with self._transactions.begin(scope, read_only=True) as session:
            link, meeting = await self._links.checked(session, token, meeting_id)
            people = await session.scalars(
                select(ParticipantRecord)
                .where(ParticipantRecord.session_id == meeting.id)
                .order_by(ParticipantRecord.created_at, ParticipantRecord.id)
            )
            notes = await session.get(NotesRecord, meeting.id)
            run = notes.findings_run_id if notes is not None else None
            findings = dict(await findings_of(session, meeting.id, run))
            lines: list[TranscriptLineRecord] | None = None
            if link.show_transcript:
                lines = list(
                    (
                        await session.scalars(
                            select(Lines)
                            .where(
                                Lines.session_id == meeting.id,
                                Lines.meeting_started_at == meeting.started_at,
                            )
                            .order_by(Lines.start_ms, Lines.seq)
                            .limit(LINES_SHOWN + 1)
                        )
                    ).all()
                )
            roles = await session.execute(
                select(SpeakerRecord.idx, SpeakerRecord.role).where(
                    SpeakerRecord.session_id == meeting.id
                )
            )
            owner_name = None
            if link.show_names:
                profile = await self._ports.get(ACCOUNT_PROFILE_READER).profile(
                    session, meeting.user_id
                )
                owner_name = profile.display_name if profile is not None else None
            return SharedPage(
                link=link, meeting=meeting,
                participants=[Person(p.name, p.email) for p in people], notes=notes,
                findings=findings, lines=None if lines is None else lines[:LINES_SHOWN],
                truncated=lines is not None and len(lines) > LINES_SHOWN,
                roles={idx: role for idx, role in roles}, owner_name=owner_name,
            )  # fmt: skip

    async def comments(self, token: str) -> list[ShareCommentRecord]:
        """The link's newest 200 comments, oldest first."""
        scope, meeting_id = await self._links.located(token)
        async with self._transactions.begin(scope, read_only=True) as session:
            link, meeting = await self._links.checked(session, token, meeting_id)
            if not link.allow_comments:
                raise CommentsClosedError
            newest = await session.scalars(
                select(ShareCommentRecord)
                .where(ShareCommentRecord.session_id == meeting.id)
                .order_by(ShareCommentRecord.created_at.desc(), ShareCommentRecord.id.desc())
                .limit(COMMENTS_SHOWN)
            )
            return list(reversed(newest.all()))

    async def comment(self, token: str, author: str | None, text: str) -> ShareCommentRecord:
        """A reader's comment under the link's page; 422 `comment_invalid` for a bad one."""
        try:
            name, body = checked_comment(author, text)
        except CommentRuleError as error:
            raise AppError(error.code, HTTPStatus.UNPROCESSABLE_ENTITY) from error
        scope, meeting_id = await self._links.located(token)
        async with self._transactions.begin(scope) as session:
            link, meeting = await self._links.checked(session, token, meeting_id)
            if not link.allow_comments:
                raise CommentsClosedError
            record = ShareCommentRecord(
                id=new_id(), session_id=meeting.id, user_id=meeting.user_id,
                org_id=meeting.org_id, author=name, text=body, created_at=self._clock(),
            )  # fmt: skip
            session.add(record)
        return record
