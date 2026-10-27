"""The transcribe stage of a recording's run (§3.4 flow 5, MT-D10, ADR 0073).

The recording is fetched to a scratch directory, its pauses found and its audio cut into
parts of at most 90 minutes, ending in a pause where there is one; a shorter recording is
one part. Each part is heard a minute past its cuts on either side. The parts go to the
transcription model through the AI port at once — at most four at a time, each under its
own effect key, `ESSENTIAL` — asking for timed segments with their speakers; a part
answered without segments is one. The segments, moved by where their part was heard from,
are kept with each part's voices as the raw transcript (O4, at most 72 hours) and named on
the run; the align stage joins the voices across the cuts and writes the meeting's lines.
A model that marks no speakers (a fallback) leaves the segments without voices, and the
stage says so in its log. A redelivered stage that finds the raw transcript named asks
nothing again.
"""

import asyncio
import json
from collections.abc import Mapping
from datetime import timedelta
from pathlib import Path
from typing import Any, Final
from uuid import UUID

import structlog

from shosai.core.ai.calls import CallClass, CallContext, CallOrigin, ModelRoute
from shosai.core.ai.port import AiProviders
from shosai.core.ai.requests import AudioFile, TranscriptionRequest
from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.ports.directory import PortDirectory
from shosai.core.storage.port import ObjectStorage
from shosai.features.notes.application.pipeline import StageFailedError, StageWork
from shosai.features.notes.application.scratch import fetched, scratch
from shosai.features.notes.application.stage_reads import cross_border, present_meeting
from shosai.features.notes.domain.recordings import Part, parts_of
from shosai.features.notes.domain.runs import effect_key
from shosai.features.notes.infrastructure.media_tools import (
    PART_MEDIA_TYPE,
    UNREADABLE,
    MediaError,
    MediaTools,
)
from shosai.features.notes.infrastructure.run_records import RunRecord

PARTS_AT_ONCE: Final = 4
# 90 минут записи Scribe отвечает примерно за 75 с; запас — на отправку и очередь провайдера.
CALL_DEADLINE: Final = timedelta(minutes=5)
log = structlog.stdlib.get_logger(__name__)


def raw_key(run_id: UUID) -> str:
    """Where a run's raw transcript (O4) is kept, for at most 72 hours."""
    return f"transient/transcript/{run_id}.json"


class TranscribeStage:
    """Turns a run's recording into its raw transcript."""

    def __init__(
        self,
        transactions: HomeTransactions,
        collaborators: tuple[PortDirectory, Mapping[Home, ObjectStorage], MediaTools],
        model: tuple[AiProviders, ModelRoute],
    ) -> None:
        self._transactions = transactions
        self._ports, self._storage, self._tools = collaborators
        self._ai, self._route = model

    async def run(self, work: StageWork) -> None:
        """Transcribe the recording and keep the raw transcript, once per run."""
        async with self._transactions.begin(work.scope, read_only=True) as session:
            meeting = await present_meeting(session, work.meeting_id)
            run = await session.get(RunRecord, work.run_id)
            consent = await cross_border(session, self._ports, meeting.user_id)
        if run is None or run.audio_key is None or not run.audio_duration_ms:
            raise StageFailedError(UNREADABLE)
        if run.raw_transcript_key is not None:
            return
        parts = await self._transcribed(
            work, (run.audio_key, run.audio_duration_ms), consent=consent
        )
        key = raw_key(work.run_id)
        body = json.dumps({"parts": parts}, ensure_ascii=False).encode()
        await self._storage[work.scope.home].put(key, body, content_type="application/json")
        async with self._transactions.begin(work.scope) as session:
            locked = await session.get(RunRecord, work.run_id, with_for_update=True)
            if locked is None:
                raise StageFailedError(UNREADABLE)
            locked.raw_transcript_key = key
        segments = [s for part in parts for s in part["segments"]]
        voiced = any(s["speaker"] is not None for s in segments)
        log.info(
            "Запись расшифрована", run_id=str(work.run_id), segments=len(segments),
            parts=len(parts), speakers_marked=voiced,
        )  # fmt: skip
        if segments and not voiced:
            log.warning("Запись расшифрована без говорящих", run_id=str(work.run_id))

    async def _transcribed(
        self, work: StageWork, recording: tuple[str, int], *, consent: bool
    ) -> list[dict[str, Any]]:
        """The recording's parts with their timed segments, in order."""
        key, duration_ms = recording
        try:
            async with scratch() as directory:
                path = await fetched(self._storage, work.scope.home, key, directory)
                cuts = parts_of(duration_ms, await self._tools.silences(path))
                heard = [part.heard(duration_ms) for part in cuts]
                files = [
                    await self._tools.cut(path, span, directory / f"part-{n}.ogg")
                    for n, span in enumerate(heard)
                ]
                gate = asyncio.Semaphore(PARTS_AT_ONCE)
                asked = await asyncio.gather(
                    *(
                        self._part(work, (n, part, span, file), gate, consent=consent)
                        for n, (part, span, file) in enumerate(zip(cuts, heard, files, strict=True))
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
        cut: tuple[int, Part, Part, Path],
        gate: asyncio.Semaphore,
        *,
        consent: bool,
    ) -> dict[str, Any]:
        number, part, heard, file = cut
        context = CallContext(
            effect_key=effect_key(work.run_id, work.stage, number), feature="notes.transcribe",
            call_class=CallClass.ESSENTIAL, origin=CallOrigin.BACKGROUND, scope=work.scope,
            cross_border_consent=consent, deadline=CALL_DEADLINE,
        )  # fmt: skip
        data = await asyncio.to_thread(file.read_bytes)
        audio = AudioFile(data, PART_MEDIA_TYPE, heard.duration_ms / 1000)
        request = TranscriptionRequest(audio, timestamps=True, speakers=True)
        async with gate:
            answer = await self._ai.transcribe(context, self._route, request)
        segments = [
            {
                "start_ms": heard.start_ms + s.start_ms,
                "end_ms": heard.start_ms + s.end_ms,
                "text": s.text,
                "speaker": s.speaker,
            }
            for s in answer.segments
            if s.text.strip()
        ]
        if not segments and answer.text.strip():
            segments = [
                {"start_ms": heard.start_ms, "end_ms": heard.end_ms, "text": answer.text,
                 "speaker": None}
            ]  # fmt: skip
        return {"start_ms": part.start_ms, "end_ms": part.end_ms, "segments": segments}
