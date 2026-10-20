"""The transcribe stage of a recording's run (§3.4 flow 5, MT-D10, ADR 0043).

The recording is fetched to a scratch directory, its pauses found and its audio cut into
parts of at most 5 minutes, ending in a pause where there is one. The parts go to the
transcription model through the AI port at once — at most four at a time, each under its
own effect key, `ESSENTIAL` — asking for timed segments; a part answered without them is
one segment. The segments, moved by their part's start, are kept as the raw transcript
(O4, for the alignment of speakers) and shaped into the meeting's lines, written once per
run with fresh `seq`s (inv-8).
"""

import asyncio
import json
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Final
from uuid import UUID

import structlog
from sqlalchemy import func, select

from shosai.core.ai.calls import CallClass, CallContext, CallOrigin, ModelRoute
from shosai.core.ai.port import AiProviders
from shosai.core.ai.requests import AudioFile, TranscriptionRequest
from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.ports.directory import PortDirectory
from shosai.core.storage.port import ObjectStorage
from shosai.features.meetings.application.pipeline import StageFailedError, StageWork
from shosai.features.meetings.application.scratch import fetched, scratch
from shosai.features.meetings.application.stage_reads import cross_border, present_meeting
from shosai.features.meetings.domain.lines import Piece, shape_lines
from shosai.features.meetings.domain.recordings import Part, parts_of
from shosai.features.meetings.domain.runs import effect_key
from shosai.features.meetings.domain.transcript import LineOrigin, fitted_text, fresh_seqs
from shosai.features.meetings.infrastructure.media_tools import (
    PART_MEDIA_TYPE,
    UNREADABLE,
    MediaError,
    MediaTools,
)
from shosai.features.meetings.infrastructure.meeting_records import (
    MeetingRecord,
    TranscriptLineRecord,
)
from shosai.features.meetings.infrastructure.run_records import RunRecord

PARTS_AT_ONCE: Final = 4
CALL_DEADLINE: Final = timedelta(minutes=2)
log = structlog.stdlib.get_logger(__name__)


def raw_key(run_id: UUID) -> str:
    """Where a run's raw transcript (O4) is kept, for at most 72 hours."""
    return f"transient/transcript/{run_id}.json"


class TranscribeStage:
    """Turns a run's recording into its meeting's lines."""

    def __init__(
        self,
        transactions: HomeTransactions,
        collaborators: tuple[PortDirectory, Mapping[Home, ObjectStorage], MediaTools],
        model: tuple[AiProviders, ModelRoute],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._ports, self._storage, self._tools = collaborators
        self._ai, self._route = model
        self._clock = clock

    async def run(self, work: StageWork) -> None:
        """Transcribe the recording and write its lines once per run."""
        async with self._transactions.begin(work.scope, read_only=True) as session:
            if await self._written(work):
                return
            meeting = await present_meeting(session, work.meeting_id)
            run = await session.get(RunRecord, work.run_id)
            consent = await cross_border(session, self._ports, meeting.user_id)
        if run is None or run.audio_key is None or not run.audio_duration_ms:
            raise StageFailedError(UNREADABLE)
        parts = await self._transcribed(
            work, (run.audio_key, run.audio_duration_ms), consent=consent
        )
        key = raw_key(work.run_id)
        body = json.dumps({"parts": parts}, ensure_ascii=False).encode()
        await self._storage[work.scope.home].put(key, body, content_type="application/json")
        pieces = [
            Piece(s["start_ms"], s["end_ms"], s["text"]) for part in parts for s in part["segments"]
        ]
        await self._write(work, shape_lines(pieces), key)

    async def _transcribed(
        self, work: StageWork, recording: tuple[str, int], *, consent: bool
    ) -> list[dict[str, Any]]:
        """The recording's parts with their timed segments, in order."""
        key, duration_ms = recording
        try:
            async with scratch() as directory:
                path = await fetched(self._storage, work.scope.home, key, directory)
                cuts = parts_of(duration_ms, await self._tools.silences(path))
                files = [
                    await self._tools.cut(path, part, directory / f"part-{n}.ogg")
                    for n, part in enumerate(cuts)
                ]
                gate = asyncio.Semaphore(PARTS_AT_ONCE)
                asked = await asyncio.gather(
                    *(
                        self._part(work, (n, part, file), gate, consent=consent)
                        for n, (part, file) in enumerate(zip(cuts, files, strict=True))
                    ),
                    return_exceptions=True,
                )
        except MediaError as error:
            raise StageFailedError(error.code) from error
        answers: list[dict[str, Any]] = []
        for answer in asked:
            if isinstance(answer, BaseException):
                raise answer
            answers.append(answer)
        return answers

    async def _part(
        self,
        work: StageWork,
        cut: tuple[int, Part, Path],
        gate: asyncio.Semaphore,
        *,
        consent: bool,
    ) -> dict[str, Any]:
        number, part, file = cut
        context = CallContext(
            effect_key=effect_key(work.run_id, work.stage, number), feature="meetings.transcribe",
            call_class=CallClass.ESSENTIAL, origin=CallOrigin.BACKGROUND, scope=work.scope,
            cross_border_consent=consent, deadline=CALL_DEADLINE,
        )  # fmt: skip
        data = await asyncio.to_thread(file.read_bytes)
        audio = AudioFile(data, PART_MEDIA_TYPE, part.duration_ms / 1000)
        async with gate:
            heard = await self._ai.transcribe(
                context, self._route, TranscriptionRequest(audio, timestamps=True)
            )
        segments = [
            {
                "start_ms": part.start_ms + s.start_ms,
                "end_ms": part.start_ms + s.end_ms,
                "text": s.text,
            }
            for s in heard.segments
            if s.text.strip()
        ]
        if not segments and heard.text.strip():
            segments = [{"start_ms": part.start_ms, "end_ms": part.end_ms, "text": heard.text}]
        return {"start_ms": part.start_ms, "end_ms": part.end_ms, "segments": segments}

    async def _written(self, work: StageWork) -> bool:
        async with self._transactions.begin(work.scope, read_only=True) as session:
            found = await session.scalar(
                select(TranscriptLineRecord.seq)
                .where(
                    TranscriptLineRecord.session_id == work.meeting_id,
                    TranscriptLineRecord.run_id == work.run_id,
                )
                .limit(1)
            )
        return found is not None

    async def _write(self, work: StageWork, lines: Sequence[Any], key: str) -> None:
        async with self._transactions.begin(work.scope) as session:
            meeting = await session.scalar(
                select(MeetingRecord).where(MeetingRecord.id == work.meeting_id).with_for_update()
            )
            run = await session.get(RunRecord, work.run_id)
            if meeting is None or run is None:
                raise StageFailedError(UNREADABLE)
            if await self._written(work):
                return
            highest = await session.scalar(
                select(func.coalesce(func.max(TranscriptLineRecord.seq), 0)).where(
                    TranscriptLineRecord.session_id == meeting.id,
                    TranscriptLineRecord.meeting_started_at == meeting.started_at,
                )
            )
            seqs = fresh_seqs(int(highest or 0), len(lines))
            session.add_all(
                TranscriptLineRecord(
                    session_id=meeting.id, seq=seq, meeting_started_at=meeting.started_at,
                    started_at=meeting.started_at + timedelta(milliseconds=line.start_ms),
                    start_ms=line.start_ms, duration_ms=line.end_ms - line.start_ms,
                    speaker_idx=None, text=fitted_text(line.text)[0],
                    origin=LineOrigin.RECORDING.value, run_id=run.id,
                )
                for seq, line in zip(seqs, lines, strict=True)
            )  # fmt: skip
            meeting.line_count, meeting.updated_at = len(lines), self._clock()
            run.raw_transcript_key = key
        log.info("Запись расшифрована", run_id=str(work.run_id), lines=len(lines))
