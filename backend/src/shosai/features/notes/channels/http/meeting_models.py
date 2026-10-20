"""The shapes of `/v1/notes` (plan step 7a; snake_case, ADR 0008): cards, pages, content.

They carry what the cabinet's library and meeting page show (`frontend/src/features/
notes/domain/types.ts`), named for the API: offsets in milliseconds, durations in
seconds, a speaker by number, findings with their evidence. Field values the domain
already checks are passed through; the shapes add no rule of their own.
"""

from datetime import date, datetime
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from shosai.features.notes.application.library import MeetingView
from shosai.features.notes.application.library_cards import MeetingCard
from shosai.features.notes.domain.findings import FindingKind
from shosai.features.notes.domain.meetings import MeetingSource, MeetingStatus
from shosai.features.notes.domain.reading import MapRow, NotesState
from shosai.features.notes.domain.templates import SectionKind
from shosai.features.notes.infrastructure.meeting_records import TranscriptLineRecord
from shosai.features.notes.infrastructure.notes_records import FindingRecord


class MeetingCardOut(BaseModel):
    """A meeting in the library: what the timeline, the grid and the list show."""

    id: UUID
    title: str
    status: MeetingStatus
    source: MeetingSource
    started_at: datetime
    ended_at: datetime | None
    seconds: int = Field(description="The meeting's length in seconds.")
    owned: bool = Field(description="Whether the reader owns the meeting.")
    folder_id: UUID | None = Field(description="The owner's folder; null for anyone else.")
    participant_names: list[str] = Field(description="Up to five participants' names.")
    participant_count: int
    summary: str | None
    key_points: list[str] = Field(description="The write-up's first three key points.")
    first_decision: str | None
    action_items: int = Field(description="How many action items the write-up lists.")
    notes: NotesState


class ParticipantOut(BaseModel):
    """A participant of the meeting."""

    id: UUID
    name: str | None
    email: str | None
    source: str


class SpeakerOut(BaseModel):
    """A speaker by number: their role and how long they spoke."""

    idx: int
    role: str
    talk_ms: int


class MeetingOut(MeetingCardOut):
    """A meeting's page: its card and what only the page shows."""

    manageable: bool = Field(description="Whether the reader may rename it and rewrite it.")
    template_id: str | None
    line_count: int
    revision: int = Field(description="The notes' revision; it grows with each write-up.")
    run_id: UUID | None = Field(description="The latest run; its progress is under /v1/me/runs.")
    participants: list[ParticipantOut]
    speakers: list[SpeakerOut]


class MeetingChangeIn(BaseModel):
    """A new title, folder or template; `null` takes the folder or the template away."""

    model_config = ConfigDict(extra="forbid")

    title: Annotated[str | None, Field(min_length=1, max_length=256)] = None
    folder_id: UUID | None = None
    template_id: Annotated[
        str | None,
        Field(
            min_length=1,
            max_length=128,
            description="A shipped template's code or your own template's id; null for Leo's.",
        ),
    ] = None


class TranscriptLineOut(BaseModel):
    """A line of the transcript: its number, offset, length, speaker and text."""

    seq: int
    start_ms: int
    duration_ms: int
    speaker: int | None = Field(description="The speaker's number; null when unknown.")
    text: str


class FindingOut(BaseModel):
    """A finding with the moment that proves it."""

    id: UUID
    kind: FindingKind
    text: str
    topic: str | None
    owner_speaker: int | None
    owner_name: str | None
    due_on: date | None
    start_ms: int
    end_ms: int
    quote: str


class SectionOut(BaseModel):
    """A section of the write-up: a summary's text, or the findings it lists."""

    kind: SectionKind
    heading_code: str | None = Field(description="A shipped heading, worded by the cabinet.")
    title: str | None = Field(description="The person's own title of the section.")
    text: str | None = None
    items: list[FindingOut] | None = None


class WriteUpOut(BaseModel):
    """Leo's write-up of the meeting by its template."""

    template_id: str
    automatic: bool = Field(description="Written after the meeting, not chosen by a person.")
    written_at: datetime | None
    revision: int
    sections: list[SectionOut]


class MapNodeOut(BaseModel):
    """A node of the mind map in pre-order: the root has no parent."""

    id: str
    parent_id: str | None
    depth: int
    label: str


def card_out(card: MeetingCard) -> dict[str, Any]:
    """A card's fields by the API's names."""
    return {
        "id": card.meeting_id, "title": card.title, "status": card.status,
        "source": card.source, "started_at": card.started_at, "ended_at": card.ended_at,
        "seconds": card.seconds, "owned": card.owned, "folder_id": card.folder_id,
        "participant_names": list(card.participant_names),
        "participant_count": card.participant_count, "summary": card.summary,
        "key_points": list(card.key_points), "first_decision": card.first_decision,
        "action_items": card.action_items, "notes": card.notes,
    }  # fmt: skip


def meeting_out(view: MeetingView) -> MeetingOut:
    """A meeting's page."""
    return MeetingOut(
        **card_out(view.card), manageable=view.manageable, template_id=view.template_id,
        line_count=view.line_count, revision=view.revision, run_id=view.run_id,
        participants=[
            ParticipantOut(id=p.participant_id, name=p.name, email=p.email, source=p.source)
            for p in view.participants
        ],
        speakers=[SpeakerOut(idx=s.idx, role=s.role, talk_ms=s.talk_ms) for s in view.speakers],
    )  # fmt: skip


def line_out(line: TranscriptLineRecord) -> TranscriptLineOut:
    """A stored line."""
    return TranscriptLineOut(
        seq=line.seq, start_ms=line.start_ms, duration_ms=line.duration_ms,
        speaker=line.speaker_idx, text=line.text,
    )  # fmt: skip


def finding_out(finding: FindingRecord) -> FindingOut:
    """A stored finding."""
    return FindingOut(
        id=finding.id, kind=FindingKind(finding.kind), text=finding.text, topic=finding.topic,
        owner_speaker=finding.owner_speaker, owner_name=finding.owner_name,
        due_on=finding.due_on, start_ms=finding.start_ms, end_ms=finding.end_ms,
        quote=finding.quote,
    )  # fmt: skip


def node_out(row: MapRow) -> MapNodeOut:
    """A node of the map."""
    parent = None if row.parent is None else str(row.parent)
    return MapNodeOut(id=str(row.index), parent_id=parent, depth=row.depth, label=row.label)
