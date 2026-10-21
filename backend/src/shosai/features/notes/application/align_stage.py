"""The align stage of a recording's run (§3.4 flow 5, MT-D3): the transcript with speakers.

The raw transcript (O4) and, when diarization succeeded, the turns (O5) are read from the
home's bucket; the speakers are laid over the segments and numbered by first appearance
(`domain/alignment.py`), and the pieces shaped into lines of about 10 seconds. In one
transaction under the meeting's lock the lines replace those the recording covers — live
lines and an earlier recording's, over its span (`audio_lead_ms` early, its length) — with
fresh `seq`s above the meeting's highest (inv-8); the meeting's speakers are written anew,
the owner of a desktop recording found by overlap with the live "me" lines; the line count
follows. Lines of the run already written mean the stage ran: nothing is written twice. A
recording without speech replaces nothing and ends the run (`transcript_empty`); a meeting
whose transcript is archived takes no lines (`transcript_archived`, step 20).
"""

import json
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any, Final
from uuid import UUID

import structlog
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.ids import new_id
from shosai.core.storage.port import ObjectStorage
from shosai.features.notes.application.pipeline import StageFailedError, StageWork
from shosai.features.notes.application.stage_reads import present_meeting
from shosai.features.notes.domain.alignment import Segment, Turn, aligned, covered, talk_times
from shosai.features.notes.domain.lines import Line, shape_lines
from shosai.features.notes.domain.transcript import (
    SIDE_SPEAKER,
    LineOrigin,
    Side,
    fitted_text,
    fresh_seqs,
)
from shosai.features.notes.infrastructure.media_tools import UNREADABLE
from shosai.features.notes.infrastructure.meeting_records import (
    MeetingRecord,
    SpeakerRecord,
    TranscriptLineRecord,
)
from shosai.features.notes.infrastructure.run_records import RunRecord

Lines = TranscriptLineRecord
EMPTY: Final = "transcript_empty"
ARCHIVED: Final = "transcript_archived"
type Json = dict[str, Any]
log = structlog.stdlib.get_logger(__name__)


def segments_of(raw: Json) -> list[Segment]:
    """The raw transcript's segments in time order; `media_unreadable` when it is malformed."""
    try:
        found = [
            Segment(int(s["start_ms"]), int(s["end_ms"]), str(s["text"]))
            for part in raw["parts"]
            for s in part["segments"]
        ]
    except (KeyError, TypeError, ValueError) as error:
        raise StageFailedError(UNREADABLE) from error
    return sorted(found, key=lambda s: (s.start_ms, s.end_ms))


def turns_of(raw: Json) -> list[Turn]:
    """The kept speaker turns; `media_unreadable` when they are malformed."""
    try:
        return [Turn(int(t["start_ms"]), int(t["end_ms"]), int(t["speaker"])) for t in raw["turns"]]
    except (KeyError, TypeError, ValueError) as error:
        raise StageFailedError(UNREADABLE) from error


class AlignStage:
    """Writes a run's recording as the meeting's transcript with speakers."""

    def __init__(
        self,
        transactions: HomeTransactions,
        storage: Mapping[Home, ObjectStorage],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._storage = storage
        self._clock = clock

    async def run(self, work: StageWork) -> None:
        """Lay the speakers over the recording's text and write its lines once per run."""
        async with self._transactions.begin(work.scope, read_only=True) as session:
            await present_meeting(session, work.meeting_id)
            run = await session.get(RunRecord, work.run_id)
        if run is None or run.raw_transcript_key is None or not run.audio_duration_ms:
            raise StageFailedError(UNREADABLE)
        home = work.scope.home
        segments = segments_of(await self._read(home, run.raw_transcript_key))
        turns = turns_of(await self._read(home, run.turns_key)) if run.turns_key else []
        lead = run.audio_lead_ms or 0
        span = covered(lead, run.audio_duration_ms)
        async with self._transactions.begin(work.scope) as session:
            meeting = await session.scalar(
                select(MeetingRecord).where(MeetingRecord.id == work.meeting_id).with_for_update()
            )
            if meeting is None:
                raise StageFailedError(UNREADABLE)
            # Расшифровка в архиве неизменна: партиции месяца может уже не быть.
            if meeting.transcript_archive_key is not None:
                raise StageFailedError(ARCHIVED)
            if await self._written(session, meeting, run.id):
                return
            me = await self._me(session, meeting, span)
            result = aligned(segments, turns, lead_ms=lead, me=me)
            lines = shape_lines(result.pieces)
            if not lines:
                # Запись без речи не стирает живых строк своего отрезка (MT-D3).
                raise StageFailedError(EMPTY)
            replaced = await self._replace(session, (meeting, run.id), span, lines)
            await self._speakers(session, meeting, (result.speakers, result.owner), lines)
            meeting.line_count = (
                await session.scalar(
                    select(func.count()).select_from(Lines).where(*self._of(meeting))
                )
                or 0
            )
            meeting.updated_at = self._clock()
        log.info(
            "Расшифровка записи выровнена",
            run_id=str(work.run_id), lines=len(lines), replaced=replaced,
            speakers=result.speakers,
        )  # fmt: skip

    async def _read(self, home: Home, key: str) -> Json:
        async with self._storage[home].open(key) as stream:
            body = b"".join([chunk async for chunk in stream.chunks(1024 * 1024)])
        try:
            loaded = json.loads(body)
        except ValueError as error:
            raise StageFailedError(UNREADABLE) from error
        if not isinstance(loaded, dict):
            raise StageFailedError(UNREADABLE)
        return loaded

    @staticmethod
    def _of(meeting: MeetingRecord) -> tuple[Any, ...]:
        return (Lines.session_id == meeting.id, Lines.meeting_started_at == meeting.started_at)

    async def _written(self, session: AsyncSession, meeting: MeetingRecord, run_id: UUID) -> bool:
        found = await session.scalar(
            select(Lines.seq).where(*self._of(meeting), Lines.run_id == run_id).limit(1)
        )
        return found is not None

    async def _me(
        self, session: AsyncSession, meeting: MeetingRecord, span: tuple[int, int]
    ) -> list[tuple[int, int]]:
        rows = await session.execute(
            select(Lines.start_ms, Lines.duration_ms).where(
                *self._of(meeting), Lines.origin == LineOrigin.LIVE.value,
                Lines.speaker_idx == SIDE_SPEAKER[Side.ME],
                Lines.start_ms >= span[0], Lines.start_ms < span[1],
            )
        )  # fmt: skip
        return [(start, start + duration) for start, duration in rows]

    async def _replace(
        self,
        session: AsyncSession,
        target: tuple[MeetingRecord, UUID],
        span: tuple[int, int],
        lines: Sequence[Line],
    ) -> int:
        """Drop the lines the recording covers, write its own; how many were dropped."""
        meeting, run_id = target
        # Через соединение: оператор ядра, и число удалённых строк известно без RETURNING.
        connection = await session.connection()
        dropped = await connection.execute(
            delete(Lines).where(
                *self._of(meeting), Lines.start_ms >= span[0], Lines.start_ms < span[1],
                or_(Lines.run_id.is_(None), Lines.run_id != run_id),
            )
        )  # fmt: skip
        count = dropped.rowcount
        highest = await session.scalar(
            select(func.coalesce(func.max(Lines.seq), 0)).where(*self._of(meeting))
        )
        session.add_all(
            Lines(
                session_id=meeting.id, seq=seq, meeting_started_at=meeting.started_at,
                org_id=meeting.org_id,
                started_at=meeting.started_at + timedelta(milliseconds=line.start_ms),
                start_ms=line.start_ms, duration_ms=line.end_ms - line.start_ms,
                speaker_idx=line.speaker, text=fitted_text(line.text)[0],
                origin=LineOrigin.RECORDING.value, run_id=run_id,
            )
            for seq, line in zip(fresh_seqs(int(highest or 0), len(lines)), lines, strict=True)
        )  # fmt: skip
        await session.flush()
        return count

    async def _speakers(
        self,
        session: AsyncSession,
        meeting: MeetingRecord,
        numbered: tuple[int, int | None],
        lines: Sequence[Line],
    ) -> None:
        count, owner = numbered
        await session.execute(delete(SpeakerRecord).where(SpeakerRecord.session_id == meeting.id))
        session.add_all(
            SpeakerRecord(
                id=new_id(), session_id=meeting.id, user_id=meeting.user_id, org_id=meeting.org_id,
                idx=idx, role="owner" if idx == owner else "numbered", talk_ms=talk,
            )
            for idx, talk in enumerate(talk_times(lines, count))
        )  # fmt: skip
