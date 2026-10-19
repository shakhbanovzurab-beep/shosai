"""The library's cards for a page of meetings, in four queries whatever the page's size.

A card shows what the library's timeline, grid and list need: the summary of the write-up,
its first three key points, its first decision and how many action items it lists, up to
five participants' names and their count, and where the notes are. The findings are the
ones the write-up lists (`findings_run_id`), ranked per meeting and kind in SQL, so a page
never reads a meeting's every finding; the participants are ranked the same way.
"""

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Final
from uuid import UUID

from sqlalchemy import and_, func, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.features.meetings.domain.findings import FindingKind
from shosai.features.meetings.domain.meetings import MeetingSource, MeetingStatus
from shosai.features.meetings.domain.reading import NotesState, notes_state, shown_folder
from shosai.features.meetings.domain.runs import RunState
from shosai.features.meetings.domain.templates import SectionKind
from shosai.features.meetings.infrastructure.meeting_records import (
    MeetingRecord,
    ParticipantRecord,
)
from shosai.features.meetings.infrastructure.notes_records import FindingRecord, NotesRecord
from shosai.features.meetings.infrastructure.run_records import RunRecord

KEY_POINTS_SHOWN: Final = 3
NAMES_SHOWN: Final = 5
CARD_KINDS: Final = (FindingKind.KEY_POINT, FindingKind.DECISION, FindingKind.ACTION_ITEM)


@dataclass(frozen=True, slots=True)
class MeetingCard:
    """A meeting as the library shows it to one reader."""

    meeting_id: UUID
    title: str
    status: MeetingStatus
    source: MeetingSource
    started_at: datetime
    ended_at: datetime | None
    seconds: int
    owned: bool
    folder_id: UUID | None
    participant_names: tuple[str, ...]
    participant_count: int
    summary: str | None
    key_points: tuple[str, ...]
    first_decision: str | None
    action_items: int
    notes: NotesState


@dataclass(slots=True)
class _Gathered:
    names: dict[UUID, list[str]] = field(default_factory=lambda: defaultdict(list))
    people: dict[UUID, int] = field(default_factory=dict)
    texts: dict[tuple[UUID, str], list[str]] = field(default_factory=lambda: defaultdict(list))
    counts: dict[tuple[UUID, str], int] = field(default_factory=dict)


def summary_of(write_up: Mapping[str, Any] | None) -> str | None:
    """The text of the write-up's summary section, if it has one."""
    for section in (write_up or {}).get("sections", []):
        if section.get("kind") == SectionKind.SUMMARY.value:
            text = section.get("text")
            return str(text) if text else None
    return None


async def _findings(
    session: AsyncSession, notes: Mapping[UUID, NotesRecord], gathered: _Gathered
) -> None:
    runs = [(m, n.findings_run_id) for m, n in notes.items() if n.findings_run_id is not None]
    if not runs:
        return
    partition = (FindingRecord.session_id, FindingRecord.kind)
    ranked = (
        select(
            FindingRecord.session_id, FindingRecord.kind, FindingRecord.text,
            func.row_number().over(partition_by=partition, order_by=FindingRecord.position)
            .label("place"),
            func.count().over(partition_by=partition).label("total"),
        )
        .where(
            tuple_(FindingRecord.session_id, FindingRecord.run_id).in_(runs),
            FindingRecord.kind.in_([kind.value for kind in CARD_KINDS]),
        )
        .subquery()
    )  # fmt: skip
    rows = await session.execute(
        select(ranked).where(ranked.c.place <= KEY_POINTS_SHOWN).order_by(ranked.c.place)
    )
    for row in rows:
        gathered.texts[row.session_id, row.kind].append(row.text)
        gathered.counts[row.session_id, row.kind] = row.total


async def _participants(
    session: AsyncSession, meeting_ids: Sequence[UUID], gathered: _Gathered
) -> None:
    name = func.coalesce(ParticipantRecord.name, func.split_part(ParticipantRecord.email, "@", 1))
    ranked = (
        select(
            ParticipantRecord.session_id, name.label("name"),
            func.row_number().over(
                partition_by=ParticipantRecord.session_id,
                order_by=(ParticipantRecord.created_at, ParticipantRecord.id),
            ).label("place"),
            func.count().over(partition_by=ParticipantRecord.session_id).label("total"),
        )
        .where(ParticipantRecord.session_id.in_(meeting_ids))
        .subquery()
    )  # fmt: skip
    rows = await session.execute(
        select(ranked).where(ranked.c.place <= NAMES_SHOWN).order_by(ranked.c.place)
    )
    for row in rows:
        gathered.names[row.session_id].append(row.name)
        gathered.people[row.session_id] = row.total


async def cards_of(
    session: AsyncSession, meetings: Sequence[MeetingRecord], reader: UUID
) -> list[MeetingCard]:
    """The cards of the meetings, in their order, as `reader` sees them."""
    ids = [meeting.id for meeting in meetings]
    if not ids:
        return []
    notes = {
        n.session_id: n
        for n in await session.scalars(select(NotesRecord).where(NotesRecord.session_id.in_(ids)))
    }
    run_ids = [m.latest_run_id for m in meetings if m.latest_run_id is not None]
    states = {
        run_id: RunState(state)
        for run_id, state in await session.execute(
            select(RunRecord.id, RunRecord.state).where(
                and_(RunRecord.id.in_(run_ids), RunRecord.session_id.in_(ids))
            )
        )
    }
    gathered = _Gathered()
    await _findings(session, notes, gathered)
    await _participants(session, ids, gathered)
    return [card(meeting, notes.get(meeting.id), states, gathered, reader) for meeting in meetings]


def card(
    meeting: MeetingRecord,
    notes: NotesRecord | None,
    states: Mapping[UUID, RunState],
    gathered: _Gathered,
    reader: UUID,
) -> MeetingCard:
    """One meeting's card from what the page gathered."""
    owned = meeting.user_id == reader
    write_up = notes.write_up if notes is not None else None
    run = states.get(meeting.latest_run_id) if meeting.latest_run_id is not None else None
    texts, counts, key = gathered.texts, gathered.counts, meeting.id
    decisions = texts.get((key, FindingKind.DECISION.value), [])
    return MeetingCard(
        meeting_id=key, title=meeting.title, status=MeetingStatus(meeting.status),
        source=MeetingSource(meeting.source), started_at=meeting.started_at,
        ended_at=meeting.ended_at, seconds=meeting.seconds, owned=owned,
        folder_id=shown_folder(meeting.folder_id, owner=owned),
        participant_names=tuple(gathered.names.get(key, [])),
        participant_count=gathered.people.get(key, 0), summary=summary_of(write_up),
        key_points=tuple(texts.get((key, FindingKind.KEY_POINT.value), [])),
        first_decision=decisions[0] if decisions else None,
        action_items=counts.get((key, FindingKind.ACTION_ITEM.value), 0),
        notes=notes_state(run, written=write_up is not None),
    )  # fmt: skip
