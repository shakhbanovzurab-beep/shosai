"""The draft's shapes of the native library and notes, as the 1.4.5 decoders read them (step 12).

A list row carries the counts the clients show; tags, hubs and the MCP flag are the draft's
and stay empty. A line's id is its `seq` as a string. A speaker's label is the person's name
for their own voice — the owner of a recording, or the live "me" side — and "Speaker N"
in their language for any other. The map's nodes are its stored tree in pre-order. The
note is the person's own notes, empty before they write any, beside Leo's write-up as
Markdown with its headings in their language and the action items it lists, each pointing
at the line its evidence starts in.
"""

from bisect import bisect_right
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Final
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from shosai.features.notes.application.native_library import NativeMeeting, NativeNote, NativeRow
from shosai.features.notes.channels.http.native_words import NativeWords
from shosai.features.notes.domain.findings import Finding, FindingKind
from shosai.features.notes.domain.meetings import MeetingStatus
from shosai.features.notes.domain.reading import map_rows
from shosai.features.notes.domain.templates import ENHANCED, SectionKind
from shosai.features.notes.domain.transcript import SIDE_SPEAKER, Side

OWNER: Final = "owner"


class SessionRow(BaseModel):
    """A meeting of the native list."""

    id: UUID
    title: str
    status: str
    started_at: datetime
    ended_at: datetime | None
    duration_ms: int
    segments_count: int
    map_nodes_count: int
    folder_id: str | None = None
    tags: list[dict[str, str]] = Field(default_factory=list)
    ephemeral: bool = False
    mcp_shared: bool = False
    hub_id: UUID | None = None
    hub_name: str | None = None


class SegmentOut(BaseModel):
    """A line of the transcript."""

    id: str
    speaker: str
    speaker_idx: int | None
    started_at: datetime
    duration_ms: int
    text: str
    confidence: float | None = None


class SessionMapNode(BaseModel):
    """A node of the meeting's map."""

    id: str
    type: str
    title: str
    parent_id: str | None
    start_offset_ms: int | None = None
    confidence: float | None = None
    origin: str = "ai"
    edited: bool = False
    position: int


class SessionFull(BaseModel):
    """A meeting with its transcript and map."""

    # Ответ всегда несёт каждое поле: клиенты черновика полагаются на `executions`.
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)

    id: UUID
    title: str
    status: str
    started_at: datetime
    ended_at: datetime | None
    segments: list[SegmentOut]
    map_nodes: list[SessionMapNode]
    executions: list[dict[str, str]] = Field(default_factory=list)
    folder_id: str | None = None
    tags: list[dict[str, str]] = Field(default_factory=list)
    ephemeral: bool = False
    mcp_shared: bool = False


class ActionItemOut(BaseModel):
    """An action item of Leo's write-up."""

    model_config = ConfigDict(validate_by_name=True)

    id: str
    text: str
    done: bool = False
    source_segment_id: str | None = Field(alias="sourceSegmentId")


class NoteOut(BaseModel):
    """The person's notes on a meeting, beside Leo's write-up."""

    model_config = ConfigDict(validate_by_name=True)

    meeting_id: UUID = Field(alias="meetingId")
    draft_markdown: str = Field(alias="draftMarkdown")
    enhanced_markdown: str | None = Field(alias="enhancedMarkdown")
    action_items: list[ActionItemOut] = Field(alias="actionItems")
    template_id: str | None = Field(alias="templateId")
    updated_at: datetime = Field(alias="updatedAt")
    version: int
    last_authoring_client: str | None = Field(alias="lastAuthoringClient")


def session_row(row: NativeRow, now: datetime | None = None) -> SessionRow:
    """A list row of the meeting."""
    meeting = row.meeting
    if meeting.status == MeetingStatus.ACTIVE.value:
        moment = now or datetime.now(UTC)
        duration = max(0, int((moment - meeting.started_at).total_seconds() * 1000))
    else:
        duration = meeting.seconds * 1000
    return SessionRow(
        id=meeting.id, title=meeting.title, status=meeting.status,
        started_at=meeting.started_at, ended_at=meeting.ended_at, duration_ms=duration,
        segments_count=meeting.line_count, map_nodes_count=row.map_nodes,
        folder_id=str(meeting.folder_id) if meeting.folder_id else None,
        ephemeral=not meeting.kept,
    )  # fmt: skip


def speaker_label(
    found: NativeMeeting, speaker: int | None, words: tuple[NativeWords, str | None]
) -> str:
    """The person's name for their own voice, "Speaker N" for another; empty for none."""
    vocabulary, language = words
    if speaker is None:
        return ""
    own = found.roles.get(speaker) == OWNER or (
        not found.roles and speaker == SIDE_SPEAKER[Side.ME]
    )
    if own and found.reader is not None:
        return found.reader.display_name
    return vocabulary.speaker(language, speaker + 1)


def session_full(found: NativeMeeting, words: NativeWords) -> SessionFull:
    """The meeting with every line and its map."""
    meeting = found.meeting
    language = found.reader.language if found.reader is not None else None
    segments = [
        SegmentOut(
            id=str(line.seq), speaker=speaker_label(found, line.speaker_idx, (words, language)),
            speaker_idx=line.speaker_idx, started_at=line.started_at,
            duration_ms=line.duration_ms, text=line.text,
        )
        for line in found.lines
    ]  # fmt: skip
    nodes = [
        SessionMapNode(
            id=str(row.index), type="root" if row.parent is None else "topic", title=row.label,
            parent_id=None if row.parent is None else str(row.parent), position=row.index,
        )
        for row in (map_rows(found.map) if found.map else [])
    ]  # fmt: skip
    return SessionFull(
        id=meeting.id, title=meeting.title, status=meeting.status,
        started_at=meeting.started_at, ended_at=meeting.ended_at, segments=segments,
        map_nodes=nodes, folder_id=str(meeting.folder_id) if meeting.folder_id else None,
        ephemeral=not meeting.kept,
    )  # fmt: skip


def enhanced_markdown(note: NativeNote, words: NativeWords) -> str | None:
    """Leo's write-up as Markdown, headings in the person's language; None before there is one."""
    if note.notes is None or note.notes.write_up is None:
        return None
    blocks: list[str] = []
    for section in note.notes.write_up.get("sections", []):
        code = section.get("heading_code") or section.get("kind", "")
        heading = section.get("title") or words.heading(note.language, str(code))
        if section.get("kind") == SectionKind.SUMMARY.value:
            body = [str(section["text"])] if section.get("text") else []
        else:
            body = [f"- {f.text}" for f in listed(note, section.get("finding_ids", []))]
        blocks.append("\n".join([f"## {heading}", *body]))
    return "\n\n".join(blocks)


def listed(note: NativeNote, ids: Sequence[str]) -> list[Finding]:
    """The findings a section lists, in its order."""
    found = (note.findings.get(UUID(raw)) for raw in ids)
    return [finding for finding in found if finding is not None]


def action_items(note: NativeNote) -> list[ActionItemOut]:
    """The write-up's action items, each pointing at the line its evidence starts in."""
    if note.notes is None or note.notes.write_up is None:
        return []
    starts = [start for _, start in note.starts]
    items: list[ActionItemOut] = []
    for section in note.notes.write_up.get("sections", []):
        for raw in section.get("finding_ids", []):
            finding = note.findings.get(UUID(raw))
            if finding is None or finding.kind is not FindingKind.ACTION_ITEM:
                continue
            at = bisect_right(starts, finding.evidence.start_ms) - 1
            line = str(note.starts[at][0]) if at >= 0 else None
            items.append(ActionItemOut(id=raw, text=finding.text, source_segment_id=line))
    return items


def note_out(note: NativeNote, words: NativeWords) -> NoteOut:
    """The draft's shape of the note."""
    own, notes = note.own, note.notes
    template = notes.write_up_template if notes is not None else None
    return NoteOut(
        meeting_id=note.meeting.id, draft_markdown=own.markdown if own else "",
        enhanced_markdown=enhanced_markdown(note, words), action_items=action_items(note),
        template_id=None if template in {None, ENHANCED} else template,
        updated_at=own.updated_at if own else note.meeting.updated_at,
        version=own.version if own else 0, last_authoring_client=own.client if own else None,
    )  # fmt: skip
