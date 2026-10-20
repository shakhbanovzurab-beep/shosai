"""Diarization and alignment of a recording's run (step 10, §3.4 flow 5, MT-D3)."""

import json
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select

from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.meetings.application.align_stage import AlignStage
from shosai.features.meetings.application.diarize_stage import turns_key
from shosai.features.meetings.application.pipeline import StageFailedError, StageWork
from shosai.features.meetings.application.run_rows import ensure_run, progress_of
from shosai.features.meetings.application.transcribe_stage import raw_key
from shosai.features.meetings.domain.runs import (
    RunSource,
    RunState,
    Stage,
    StageStatus,
    idempotency_key,
)
from shosai.features.meetings.infrastructure.meeting_records import (
    MeetingRecord,
    SpeakerRecord,
    TranscriptLineRecord,
)
from shosai.features.meetings.infrastructure.run_records import RunRecord
from tests.features.meetings.recording_bench import RecordingBench
from tests.features.meetings.test_imports import TRANSCRIPTIONS, heard, imported, run_and_meeting

type Json = dict[str, Any]
ME, THEM = 0, 1


async def recorded(
    bench: RecordingBench,
    owner: uuid.UUID,
    live: list[tuple[int, int, int, str]],
    recording: tuple[int, int, Json, list[Json]],
) -> StageWork:
    """A live meeting with its lines and a desktop recording's run, transcribed and diarized."""
    lead_ms, duration_ms, raw, turns = recording
    started = bench.clock.now - timedelta(hours=2)
    async with bench.homes.transactions.begin(TenancyScope(Home.EU, owner)) as session:
        meeting = MeetingRecord(
            id=uuid.uuid4(), user_id=owner, title="Call", status="completed", source="live",
            started_at=started, ended_at=started + timedelta(minutes=10), seconds=600,
        )  # fmt: skip
        session.add(meeting)
        await session.flush()
        session.add_all(
            TranscriptLineRecord(
                session_id=meeting.id, seq=seq, meeting_started_at=started,
                started_at=started + timedelta(milliseconds=start), start_ms=start,
                duration_ms=duration, speaker_idx=speaker, text=text, origin="live",
            )
            for seq, (start, duration, speaker, text) in enumerate(live, 1)
        )  # fmt: skip
        meeting.line_count = len(live)
        run_id = await ensure_run(
            session, meeting, RunSource.RECORDING, idempotency_key(RunSource.RECORDING)
        )
        run = await session.get(RunRecord, run_id)
        assert run is not None
        run.audio_lead_ms, run.audio_duration_ms = lead_ms, duration_ms
        run.raw_transcript_key, run.turns_key = raw_key(run_id), turns_key(run_id)
    objects = bench.storage[Home.EU]
    kind = "application/json"
    await objects.put(raw_key(run_id), json.dumps(raw).encode(), content_type=kind)
    await objects.put(turns_key(run_id), json.dumps({"turns": turns}).encode(), content_type=kind)
    scope = TenancyScope(Home.EU, owner)
    return StageWork(scope, run_id, meeting.id, RunSource.RECORDING, Stage.ALIGN, 1)


async def transcript(
    bench: RecordingBench, work: StageWork
) -> tuple[list[tuple[int, int, int | None, str, str]], list[tuple[int, str, int]], int]:
    """The meeting's lines `(seq, start, speaker, origin, text)`, speakers and line count."""
    async with bench.homes.transactions.begin(work.scope) as session:
        lines = await session.execute(
            select(
                TranscriptLineRecord.seq, TranscriptLineRecord.start_ms,
                TranscriptLineRecord.speaker_idx, TranscriptLineRecord.origin,
                TranscriptLineRecord.text,
            )
            .where(TranscriptLineRecord.session_id == work.meeting_id)
            .order_by(TranscriptLineRecord.start_ms, TranscriptLineRecord.seq)
        )  # fmt: skip
        speakers = await session.execute(
            select(SpeakerRecord.idx, SpeakerRecord.role, SpeakerRecord.talk_ms)
            .where(SpeakerRecord.session_id == work.meeting_id)
            .order_by(SpeakerRecord.idx)
        )
        meeting = await session.get(MeetingRecord, work.meeting_id)
    assert meeting is not None
    found = [(seq, start, speaker, origin, text) for seq, start, speaker, origin, text in lines]
    voices = [(idx, role, talk) for idx, role, talk in speakers]
    return found, voices, meeting.line_count


def segment(start: float, end: float, text: str) -> Json:
    return {"start_ms": int(start * 1000), "end_ms": int(end * 1000), "text": text}


def turn(start: float, end: float, speaker: int) -> Json:
    return {"start_ms": int(start * 1000), "end_ms": int(end * 1000), "speaker": speaker}


async def test_a_failed_diarization_leaves_a_transcript_without_speakers_and_a_partial_run(
    recording_bench: RecordingBench, video: Path
) -> None:
    owner = uuid.uuid4()
    for _ in range(2):
        recording_bench.ai.openrouter.answer(TRANSCRIPTIONS, heard())
    recording_bench.ai.pyannote.failing["diarize"] = 500

    started = await imported(
        recording_bench, owner, await recording_bench.upload(owner, video, "video/mp4")
    )
    ran = await recording_bench.drive()

    run, meeting = await run_and_meeting(recording_bench, owner, started)
    scope = TenancyScope(Home.EU, owner)
    work = StageWork(scope, run.id, meeting.id, RunSource.IMPORT, Stage.ALIGN, 1)
    lines, speakers, count = await transcript(recording_bench, work)
    diarize = progress_of(run.stage_state)[Stage.DIARIZE]
    assert ran.count(Stage.DIARIZE) == 3
    assert (diarize.status, diarize.error_code) == (StageStatus.FAILED, "provider_error")
    assert RunState(run.state) is RunState.PARTIALLY_COMPLETED
    assert (len(lines), count, speakers) == (4, 4, [])
    assert {speaker for _, _, speaker, _, _ in lines} == {None}
    assert run.turns_key is None


async def test_four_voices_give_four_numbered_speakers_and_lines_of_about_ten_seconds(
    recording_bench: RecordingBench,
) -> None:
    owner = uuid.uuid4()
    voices = [(0, 2), (30, 0), (60, 3), (90, 1)]
    segments = [
        segment(begin + 5 * n, begin + 5 * n + 5, f"Voice {voice}, sentence {n}.")
        for begin, voice in voices
        for n in range(5)
    ]
    turns = [turn(begin, begin + 25, voice) for begin, voice in voices]
    work = await recorded(
        recording_bench, owner, [], (0, 120_000, {"parts": [{"segments": segments}]}, turns)
    )

    await AlignStage(recording_bench.homes.transactions, recording_bench.storage).run(work)

    lines, speakers, count = await transcript(recording_bench, work)
    by_voice = [[start for _, start, speaker, _, _ in lines if speaker == n] for n in range(4)]
    assert [(idx, role) for idx, role, _ in speakers] == [(n, "numbered") for n in range(4)]
    assert [first[0] for first in by_voice] == [0, 30_000, 60_000, 90_000]
    assert all(
        starts == [b, b + 10_000, b + 20_000]
        for starts, b in zip(by_voice, [0, 30_000, 60_000, 90_000], strict=True)
    )
    assert count == len(lines) == 12
    assert {talk for _, _, talk in speakers} == {25_000}


async def test_a_desktop_recording_replaces_the_live_lines_it_covers_and_finds_the_owner(
    recording_bench: RecordingBench,
) -> None:
    owner = uuid.uuid4()
    live = [
        (2_000, 3_000, ME, "Before the recording."),
        (10_000, 8_000, ME, "Live me."),
        (25_000, 8_000, THEM, "Live them."),
        (400_000, 5_000, THEM, "After the recording."),
    ]
    segments = [segment(5, 13, "Recorded me."), segment(20, 28, "Recorded them.")]
    turns = [turn(4, 14, 1), turn(19, 29, 0)]
    # Запись началась через 5 секунд после встречи: её время плюс 5 секунд — время встречи.
    work = await recorded(
        recording_bench, owner, live, (-5_000, 60_000, {"parts": [{"segments": segments}]}, turns)
    )
    stage = AlignStage(recording_bench.homes.transactions, recording_bench.storage)

    await stage.run(work)
    first = await transcript(recording_bench, work)
    await stage.run(work)
    again = await transcript(recording_bench, work)

    lines, speakers, count = first
    assert [(start, speaker, origin, text) for _, start, speaker, origin, text in lines] == [
        (2_000, ME, "live", "Before the recording."),
        (10_000, 0, "recording", "Recorded me."),
        (25_000, 1, "recording", "Recorded them."),
        (400_000, THEM, "live", "After the recording."),
    ]  # fmt: skip
    assert [seq for seq, *_ in lines[1:3]] == [5, 6]
    assert [(idx, role) for idx, role, _ in speakers] == [(0, "owner"), (1, "numbered")]
    assert count == 4
    assert again == first


async def test_a_recording_without_speech_keeps_the_live_lines_and_fails(
    recording_bench: RecordingBench,
) -> None:
    owner = uuid.uuid4()
    live = [(10_000, 8_000, ME, "Live me.")]
    work = await recorded(
        recording_bench, owner, live, (0, 60_000, {"parts": [{"segments": []}]}, [])
    )

    with pytest.raises(StageFailedError) as failed:
        await AlignStage(recording_bench.homes.transactions, recording_bench.storage).run(work)

    lines, speakers, count = await transcript(recording_bench, work)
    assert failed.value.code == "transcript_empty"
    assert ([text for *_, text in lines], speakers, count) == (["Live me."], [], 1)
