"""An uploaded recording becomes a meeting with its transcript (step 9a, §3.4 flow 5)."""

import json
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Any, Final

import httpx
from sqlalchemy import select

from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.files.infrastructure.upload_records import UploadRecord
from shosai.features.meetings.application.diarize_stage import turns_key
from shosai.features.meetings.application.run_rows import progress_of
from shosai.features.meetings.application.transcribe_stage import raw_key
from shosai.features.meetings.domain.runs import STAGES, RunSource, RunState, Stage, StageStatus
from shosai.features.meetings.infrastructure.meeting_records import (
    MeetingRecord,
    SpeakerRecord,
    TranscriptLineRecord,
)
from shosai.features.meetings.infrastructure.notes_records import SettingsRecord
from shosai.features.meetings.infrastructure.run_records import RunRecord
from tests.features.billing.people_bench import bearer
from tests.features.meetings.recording_bench import VIDEO_SECONDS, RecordingBench, ffmpeg
from tests.harness.connections import fetch_rows
from tests.harness.run_slot import RunSlot

TRANSCRIPTIONS = "audio/transcriptions"
# Голоса записи: первый говорит в начале каждой части, второй — с её двадцатой секунды.
TWO_VOICES: Final = [
    {"speaker": "SPEAKER_03", "start": 0.0, "end": 12.0},
    {"speaker": "SPEAKER_01", "start": 15.0, "end": 30.0},
    {"speaker": "SPEAKER_03", "start": 290.0, "end": 312.0},
    {"speaker": "SPEAKER_01", "start": 314.0, "end": 330.0},
]
type Json = dict[str, Any]


def heard() -> httpx.Response:
    """A part's answer: two timed sentences, the second after a long pause."""
    segments = [
        {"start": 0.0, "end": 4.0, "text": " Hello, team."},
        {"start": 20.0, "end": 26.0, "text": "Let us start."},
    ]
    return httpx.Response(
        200,
        json={
            "text": "Hello, team. Let us start.", "language": "english", "segments": segments,
            "usage": {"seconds": 150.0, "cost": 0.0011},
        },
    )  # fmt: skip


async def imported(bench: RecordingBench, owner: uuid.UUID, upload_id: uuid.UUID) -> Json:
    """The import's answer, 202 expected."""
    response = await bench.http.post(
        "/v1/meetings/imports", json={"upload_id": str(upload_id)}, headers=bearer((Home.EU, owner))
    )
    assert response.status_code == 202, response.text
    body: Json = response.json()
    return body


async def run_and_meeting(
    bench: RecordingBench, owner: uuid.UUID, started: Json
) -> tuple[RunRecord, MeetingRecord]:
    async with bench.homes.transactions.begin(TenancyScope(Home.EU, owner)) as session:
        run = await session.get(RunRecord, uuid.UUID(started["run_id"]))
        meeting = await session.get(MeetingRecord, uuid.UUID(started["meeting_id"]))
    assert run is not None
    assert meeting is not None
    return run, meeting


async def failed_with(bench: RecordingBench, owner: uuid.UUID, path: Path, kind: str) -> str:
    """The code the intake ended an import of the file with; nothing was sent to a model."""
    started = await imported(bench, owner, await bench.upload(owner, path, kind))

    ran = await bench.drive()

    run, meeting = await run_and_meeting(bench, owner, started)
    intake = progress_of(run.stage_state)[Stage.INTAKE]
    assert ran == [Stage.INTAKE]
    assert (RunState(run.state), intake.status) == (RunState.FAILED, StageStatus.FAILED)
    assert (meeting.seconds, meeting.line_count) == (0, 0)
    assert bench.ai.openrouter.requests == []
    return str(intake.error_code)


async def test_a_video_becomes_a_meeting_with_its_transcript_and_a_repeat_answers_the_same(
    recording_bench: RecordingBench, video: Path, run_slot: RunSlot
) -> None:
    owner = uuid.uuid4()
    upload_id = await recording_bench.upload(owner, video, "video/mp4")
    for _ in range(2):
        recording_bench.ai.openrouter.answer(TRANSCRIPTIONS, heard())
    recording_bench.ai.pyannote.turns = TWO_VOICES

    started = await imported(recording_bench, owner, upload_id)
    again = await imported(recording_bench, owner, upload_id)
    ran = await recording_bench.drive()

    run, meeting = await run_and_meeting(recording_bench, owner, started)
    async with recording_bench.storage[Home.EU].open(raw_key(run.id)) as stream:
        raw = json.loads(b"".join([chunk async for chunk in stream.chunks(1 << 20)]))
    async with recording_bench.homes.transactions.begin(TenancyScope(Home.EU, owner)) as session:
        lines = (
            await session.scalars(
                select(TranscriptLineRecord)
                .where(TranscriptLineRecord.session_id == meeting.id)
                .order_by(TranscriptLineRecord.seq)
            )
        ).all()
    async with recording_bench.homes.transactions.begin(TenancyScope(Home.EU, owner)) as session:
        found = await session.execute(
            select(SpeakerRecord.idx, SpeakerRecord.role, SpeakerRecord.talk_ms)
            .where(SpeakerRecord.session_id == meeting.id)
            .order_by(SpeakerRecord.idx)
        )
        speakers = [(idx, role, talk) for idx, role, talk in found]
    costs = await fetch_rows(
        run_slot.claimed.connections[Home.EU],
        "SELECT feature, kind, outcome, unit FROM provider_costs ORDER BY feature, created_at",
    )
    bodies = recording_bench.ai.openrouter.bodies(TRANSCRIPTIONS)
    second = raw["parts"][1]["start_ms"]
    assert again == started
    assert ran == list(STAGES[RunSource.IMPORT])
    assert RunState(run.state) is RunState.SUCCEEDED
    assert (meeting.title, meeting.source, meeting.seconds) == ("meeting", "import", VIDEO_SECONDS)
    assert meeting.ended_at is not None
    assert meeting.ended_at - meeting.started_at == timedelta(seconds=VIDEO_SECONDS)
    assert abs(second - 297_000) < 1_500
    assert [(p["start_ms"], p["end_ms"]) for p in raw["parts"]] == [
        (0, second), (second, run.audio_duration_ms),
    ]  # fmt: skip
    assert [(line.start_ms, line.text, line.speaker_idx) for line in lines] == [
        (0, "Hello, team.", 0), (20_000, "Let us start.", 1),
        (second, "Hello, team.", 0), (second + 20_000, "Let us start.", 1),
    ]  # fmt: skip
    assert {(line.run_id, line.origin) for line in lines} == {(run.id, "recording")}
    assert (meeting.line_count, run.raw_transcript_key) == (4, raw_key(run.id))
    assert run.turns_key == turns_key(run.id)
    assert speakers == [(0, "numbered", 8_000), (1, "numbered", 12_000)]
    assert [(b["input_audio"]["format"], b["response_format"]) for b in bodies] == [
        ("ogg", "verbose_json"), ("ogg", "verbose_json"),
    ]  # fmt: skip
    assert [tuple(row.values()) for row in costs] == [
        ("meetings.diarize", "diarize", "ok", "audio_second"),
        *[("meetings.transcribe", "transcribe", "ok", "audio_second")] * 2,
    ]


async def test_a_recording_longer_than_the_minutes_left_fails_before_any_paid_call(
    recording_bench: RecordingBench, video: Path
) -> None:
    owner = uuid.uuid4()
    async with recording_bench.homes.transactions.begin(TenancyScope(Home.EU, owner)) as session:
        await recording_bench.minutes.meeting_deleted(
            session, owner, (uuid.uuid4(), recording_bench.clock.now), 115 * 60
        )

    code = await failed_with(recording_bench, owner, video, "video/mp4")

    assert code == "upload_exceeds_minutes"


async def test_a_header_claiming_seven_hours_fails_before_any_paid_call(
    recording_bench: RecordingBench, seven_hours: Path
) -> None:
    code = await failed_with(recording_bench, uuid.uuid4(), seven_hours, "audio/mp4")

    assert code == "recording_too_long"


async def test_a_picture_is_refused_from_its_header_before_it_is_decoded(
    recording_bench: RecordingBench, tmp_path: Path
) -> None:
    picture = tmp_path / "frame.gif"
    ffmpeg("-f", "lavfi", "-i", "testsrc2=size=32x32", "-frames:v", "1", str(picture))

    code = await failed_with(recording_bench, uuid.uuid4(), picture, "video/mp4")

    assert code == "unsupported_audio_format"


async def test_another_person_s_upload_or_one_who_keeps_no_meetings_makes_none(
    recording_bench: RecordingBench, video: Path
) -> None:
    owner, stranger, private = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    theirs = await recording_bench.upload(owner, video, "video/mp4")
    kept_none = await recording_bench.upload(private, video, "video/mp4")
    async with recording_bench.homes.transactions.begin(TenancyScope(Home.EU, private)) as session:
        session.add(SettingsRecord(user_id=private, keep_meetings=False))

    taken = await recording_bench.http.post(
        "/v1/meetings/imports", json={"upload_id": str(theirs)}, headers=bearer((Home.EU, stranger))
    )
    refused = await recording_bench.http.post(
        "/v1/meetings/imports",
        json={"upload_id": str(kept_none)},
        headers=bearer((Home.EU, private)),
    )

    async with recording_bench.homes.transactions.begin(TenancyScope(Home.EU, private)) as session:
        meetings = (await session.scalars(select(MeetingRecord.id))).all()
        upload = await session.get(UploadRecord, kept_none)
    assert (taken.status_code, taken.json()["error"]["code"]) == (409, "upload_not_claimable")
    assert (refused.status_code, refused.json()["error"]["code"]) == (409, "meetings_not_kept")
    assert meetings == []
    assert upload is not None
    assert upload.state == "ready"
    assert recording_bench.sent.payloads == []
