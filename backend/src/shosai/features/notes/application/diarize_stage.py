"""The diarize stage of a recording's run (§3.4 flow 5, ADR 0043): who spoke when.

The recording is fetched to a scratch directory and its audio taken out whole as mono Opus
at 16 kHz — the smallest copy pyannote hears as well as the original — and sent once
through the AI port (`ESSENTIAL`, `meetings:{run}:diarize:0`), pyannote counting the
speakers itself. The turns are kept as O5 (`transient/turns/{run}.json`, at most 72 hours)
and named on the run. The stage is not critical: when it fails, the align stage writes the
transcript without speakers and the run ends partially completed. A redelivered stage that
finds the turns named asks nothing again.
"""

import asyncio
import json
from collections.abc import Mapping
from datetime import timedelta
from typing import Final
from uuid import UUID

import structlog

from shosai.core.ai.calls import CallClass, CallContext, CallOrigin, ModelRoute
from shosai.core.ai.port import AiProviders
from shosai.core.ai.requests import AudioFile, DiarizationRequest
from shosai.core.ai.results import SpeakerTurn
from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.ports.directory import PortDirectory
from shosai.core.storage.port import ObjectStorage
from shosai.features.notes.application.pipeline import StageFailedError, StageWork
from shosai.features.notes.application.scratch import fetched, scratch
from shosai.features.notes.application.stage_reads import cross_border, present_meeting
from shosai.features.notes.domain.recordings import Part
from shosai.features.notes.domain.runs import effect_key
from shosai.features.notes.infrastructure.media_tools import (
    PART_MEDIA_TYPE,
    UNREADABLE,
    MediaError,
    MediaTools,
)
from shosai.features.notes.infrastructure.run_records import RunRecord

# Задача стадии живёт 15 минут: на выгрузку и ожидание задания pyannote — 11 из них.
CALL_DEADLINE: Final = timedelta(minutes=11)
log = structlog.stdlib.get_logger(__name__)


def turns_key(run_id: UUID) -> str:
    """Where a run's speaker turns (O5) are kept, for at most 72 hours."""
    return f"transient/turns/{run_id}.json"


class DiarizeStage:
    """Finds who spoke when in a run's recording."""

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
        """Diarize the recording and keep the turns, once per run."""
        async with self._transactions.begin(work.scope, read_only=True) as session:
            meeting = await present_meeting(session, work.meeting_id)
            run = await session.get(RunRecord, work.run_id)
            consent = await cross_border(session, self._ports, meeting.user_id)
        if run is None or run.audio_key is None or not run.audio_duration_ms:
            raise StageFailedError(UNREADABLE)
        if run.turns_key is not None:
            return
        turns = await self._heard(work, (run.audio_key, run.audio_duration_ms), consent=consent)
        key = turns_key(work.run_id)
        body = json.dumps(
            {
                "turns": [
                    {"start_ms": t.start_ms, "end_ms": t.end_ms, "speaker": t.speaker}
                    for t in turns
                ]
            }
        ).encode()
        await self._storage[work.scope.home].put(key, body, content_type="application/json")
        async with self._transactions.begin(work.scope) as session:
            locked = await session.get(RunRecord, work.run_id, with_for_update=True)
            if locked is None:
                raise StageFailedError(UNREADABLE)
            locked.turns_key = key
        speakers = len({turn.speaker for turn in turns})
        log.info("Говорящие размечены", run_id=str(work.run_id), speakers=speakers)

    async def _heard(
        self, work: StageWork, recording: tuple[str, int], *, consent: bool
    ) -> tuple[SpeakerTurn, ...]:
        key, duration_ms = recording
        try:
            async with scratch() as directory:
                path = await fetched(self._storage, work.scope.home, key, directory)
                voice = await self._tools.cut(path, Part(0, duration_ms), directory / "voice.ogg")
                data = await asyncio.to_thread(voice.read_bytes)
        except MediaError as error:
            raise StageFailedError(error.code) from error
        context = CallContext(
            effect_key=effect_key(work.run_id, work.stage, 0), feature="notes.diarize",
            call_class=CallClass.ESSENTIAL, origin=CallOrigin.BACKGROUND, scope=work.scope,
            cross_border_consent=consent, deadline=CALL_DEADLINE,
        )  # fmt: skip
        audio = AudioFile(data, PART_MEDIA_TYPE, duration_ms / 1000)
        heard = await self._ai.diarize(context, self._route, DiarizationRequest(audio))
        return heard.turns
