"""What other slices may use of meetings (meetings plan §3.2).

Capture binds a live socket to a meeting through `LiveMeetings`, writes the live transcript
through `TranscriptStore` and tells meetings, through `LiveSignal`, when each live meeting
last sent audio and the highest line it showed (MT-D2, inv-6). Workspaces, Leo, knowledge,
hubs and commitments read meetings a viewer may read through `MeetingReader` and their
findings through `MeetingFindings`, both inside workspaces' access policy (inv-14). The
events are in `contracts.events`.
"""

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from http import HTTPStatus
from typing import Final, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.kernel.errors import AppError
from shosai.core.kernel.homes import Home
from shosai.core.ports.keys import PortKey
from shosai.features.meetings.domain.findings import FindingKind
from shosai.features.meetings.domain.meetings import MeetingStatus
from shosai.features.meetings.domain.transcript import LineOrigin, Side, checked_seq
from shosai.features.workspaces.contracts import Viewer

__all__ = [
    "LIVE_MEETINGS",
    "LIVE_SIGNAL",
    "MEETING_FINDINGS",
    "MEETING_READER",
    "TRANSCRIPT_STORE",
    "AppendOutcome",
    "FindingFacts",
    "FindingKind",
    "LineOrigin",
    "LiveLine",
    "LiveMeeting",
    "LiveMeetings",
    "LiveSignal",
    "MeetingFacts",
    "MeetingFindings",
    "MeetingNotFoundError",
    "MeetingReader",
    "MeetingStatus",
    "ParticipantFacts",
    "Side",
    "StoredLine",
    "TranscriptPage",
    "TranscriptStore",
]


class MeetingNotFoundError(AppError):
    """No such meeting the caller may use: missing, someone else's or not active (404)."""

    def __init__(self) -> None:
        super().__init__("meeting_not_found", HTTPStatus.NOT_FOUND)


@dataclass(frozen=True, slots=True)
class LiveMeeting:
    """A meeting a socket is bound to: its title, whether it is kept and when it must end."""

    meeting_id: UUID
    title: str
    kept: bool
    started_at: datetime
    # Начало + 6 часов: за 10 минут capture предупреждает, затем перестаёт брать звук.
    ends_by: datetime


class LiveMeetings(Protocol):
    """Binds a live socket to the person's active meeting (`session.start`)."""

    async def bind(self, session: AsyncSession, user_id: UUID, meeting_id: UUID) -> LiveMeeting:
        """The person's active meeting; `MeetingNotFoundError` for any other."""
        ...


@dataclass(frozen=True, slots=True)
class LiveLine:
    """A live phrase as capture queued it: its `seq`, its start, length, side and text."""

    meeting_id: UUID
    seq: int
    started_at: datetime
    duration_ms: int
    side: Side
    text: str

    def __post_init__(self) -> None:
        checked_seq(self.seq)
        if self.duration_ms < 0:
            message = "длительность строки — от нуля"
            raise ValueError(message)


@dataclass(frozen=True, slots=True)
class AppendOutcome:
    """What a batch did: lines stored, replays ignored, lines refused (meeting not kept)."""

    stored: int
    replayed: int
    refused: int


@dataclass(frozen=True, slots=True)
class StoredLine:
    """A transcript line as stored: its `seq`, offset, length, speaker, text and origin."""

    seq: int
    start_ms: int
    duration_ms: int
    speaker: int | None
    text: str
    origin: LineOrigin


class TranscriptStore(Protocol):
    """The live transcript's store: the WS drain writes through it (§11.1, §14 rule 5)."""

    async def append(self, home: Home, lines: Sequence[LiveLine]) -> AppendOutcome:
        """Store a batch in the meetings' home; a replayed `seq` is ignored, never an error."""
        ...

    async def tail(
        self, session: AsyncSession, meeting_id: UUID, limit: int
    ) -> Sequence[StoredLine]:
        """The meeting's last lines, oldest first, for `transcript.restore`."""
        ...


class LiveSignal(Protocol):
    """What capture knows of its live meetings; bound by capture (MT-D2)."""

    async def last_audio(self, meeting_ids: Collection[UUID]) -> Mapping[UUID, datetime]:
        """When each meeting last sent audio; a meeting capture does not hold is absent."""
        ...

    async def highest_shown(self, meeting_id: UUID) -> int | None:
        """The highest `seq` capture showed in the meeting, if it holds it (inv-6)."""
        ...


@dataclass(frozen=True, slots=True)
class ParticipantFacts:
    """A participant: a name if known and the address, for mapping people to members."""

    name: str | None
    email: str | None


@dataclass(frozen=True, slots=True)
class MeetingFacts:
    """A meeting the viewer may read, as other slices see it."""

    meeting_id: UUID
    user_id: UUID | None
    org_id: UUID | None
    title: str
    status: MeetingStatus
    started_at: datetime
    ended_at: datetime | None
    seconds: int
    participants: tuple[ParticipantFacts, ...]
    summary: str | None


@dataclass(frozen=True, slots=True)
class TranscriptPage:
    """A page of a meeting's transcript and the cursor of the next one."""

    lines: tuple[StoredLine, ...]
    next_cursor: str | None


class MeetingReader(Protocol):
    """Meetings a viewer may read, through workspaces' access policy (inv-14).

    A deleted meeting, a meeting not kept and a meeting of an account in identity's
    deletion window are read by nobody.
    """

    async def facts(
        self, session: AsyncSession, viewer: Viewer, meeting_ids: Collection[UUID]
    ) -> Mapping[UUID, MeetingFacts]:
        """The readable ones among `meeting_ids`; the others are absent."""
        ...

    async def transcript(
        self,
        session: AsyncSession,
        viewer: Viewer,
        meeting_id: UUID,
        cursor: str | None,
        limit: int,
    ) -> TranscriptPage:
        """A page of a readable meeting's transcript; `MeetingNotFoundError` otherwise."""
        ...

    async def readable(
        self, session: AsyncSession, viewer: Viewer, meeting_ids: Collection[UUID]
    ) -> frozenset[UUID]:
        """The readable ones among `meeting_ids`, in one query (search hits, Leo)."""
        ...


@dataclass(frozen=True, slots=True)
class FindingFacts:
    """A finding of a meeting's current notes, with its evidence."""

    finding_id: UUID
    kind: FindingKind
    text: str
    topic: str | None
    owner_name: str | None
    due_on: date | None
    start_ms: int
    end_ms: int
    quote: str


class MeetingFindings(Protocol):
    """The findings of a meeting the viewer may read."""

    async def of(
        self, session: AsyncSession, viewer: Viewer, meeting_id: UUID
    ) -> Sequence[FindingFacts]:
        """In the meeting's order; `MeetingNotFoundError` for a meeting the viewer cannot read."""
        ...


LIVE_MEETINGS: Final = PortKey[LiveMeetings]("meetings.live_meetings")
TRANSCRIPT_STORE: Final = PortKey[TranscriptStore]("meetings.transcript_store")
# Привязывает capture; пока его нет, признак жизни встречи — её последняя строка.
LIVE_SIGNAL: Final = PortKey[LiveSignal]("meetings.live_signal")
MEETING_READER: Final = PortKey[MeetingReader]("meetings.meeting_reader")
MEETING_FINDINGS: Final = PortKey[MeetingFindings]("meetings.meeting_findings")
