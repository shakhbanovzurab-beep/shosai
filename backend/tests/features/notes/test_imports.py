"""An uploaded recording becomes a meeting with its transcript and speakers (steps 9a, 29)."""

import json
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy import select

from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.files.infrastructure.upload_records import UploadRecord
from shosai.features.notes.application.run_rows import progress_of
from shosai.features.notes.application.transcribe_stage import raw_key
from shosai.features.notes.domain import recordings
from shosai.features.notes.domain.runs import STAGES, RunSource, RunState, Stage, StageStatus
from shosai.features.notes.infrastructure.meeting_records import (
    MeetingRecord,
    SpeakerRecord,
    TranscriptLineRecord,
)
from shosai.features.notes.infrastructure.notes_records import SettingsRecord
from shosai.features.notes.infrastructure.run_records import RunRecord
from tests.features.billing.people_bench import bearer
from tests.features.notes.recording_bench import VIDEO_SECONDS, RecordingBench, ffmpeg
from tests.features.notes.scribe_answers import by_length, scribe
from tests.harness.connections import fetch_rows
from tests.harness.run_slot import RunSlot

TRANSCRIPTIONS = "audio/transcriptions"
type Json = dict[str, Any]


def heard() -> httpx.Response:
    """A part's answer: two voices, the second after a long pause."""
    return scribe((0.0, 4.0, 0, "Hello, team."), (20.0, 26.0, 1, "Let us start."))


async def imported(bench: RecordingBench, owner: uuid.UUID, upload_id: uuid.UUID) -> Json:
    """The import's answer, 202 expected."""
    response = await bench.http.post(
        "/v1/notes/imports", json={"upload_id": str(upload_id)}, headers=bearer((Home.EU, owner))
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


async def lines_and_speakers(
    bench: RecordingBench, owner: uuid.UUID, meeting: MeetingRecord
) -> tuple[list[tuple[int, str, int | None]], list[tuple[int, str, int]]]:
    """The meeting's lines `(start, text, speaker)` and its speakers `(idx, role, talk)`."""
    async with bench.homes.transactions.begin(TenancyScope(Home.EU, owner)) as session:
        lines = (
            await session.scalars(
                select(TranscriptLineRecord)
                .where(TranscriptLineRecord.session_id == meeting.id)
                .order_by(TranscriptLineRecord.seq)
            )
        ).all()
        found = await session.execute(
            select(SpeakerRecord.idx, SpeakerRecord.role, SpeakerRecord.talk_ms)
            .where(SpeakerRecord.session_id == meeting.id)
            .order_by(SpeakerRecord.idx)
        )
        speakers = [(idx, role, talk) for idx, role, talk in found]
    assert {(line.run_id, line.origin) for line in lines} <= {(meeting.latest_run_id, "recording")}
    return [(line.start_ms, line.text, line.speaker_idx) for line in lines], speakers


async def raw_of(bench: RecordingBench, run: RunRecord) -> Json:
    """The run's raw transcript (O4)."""
    async with bench.storage[Home.EU].open(raw_key(run.id)) as stream:
        raw: Json = json.loads(b"".join([chunk async for chunk in stream.chunks(1 << 20)]))
    return raw


async def test_a_video_becomes_a_meeting_with_its_speakers_and_a_repeat_answers_the_same(
    recording_bench: RecordingBench, video: Path, run_slot: RunSlot
) -> None:
    owner = uuid.uuid4()
    upload_id = await recording_bench.upload(owner, video, "video/mp4")
    recording_bench.ai.openrouter.answer(TRANSCRIPTIONS, heard())

    started = await imported(recording_bench, owner, upload_id)
    again = await imported(recording_bench, owner, upload_id)
    ran = await recording_bench.drive()

    run, meeting = await run_and_meeting(recording_bench, owner, started)
    raw = await raw_of(recording_bench, run)
    lines, speakers = await lines_and_speakers(recording_bench, owner, meeting)
    costs = await fetch_rows(
        run_slot.claimed.connections[Home.EU],
        "SELECT feature, kind, outcome, unit FROM provider_costs ORDER BY feature, created_at",
    )
    [body] = recording_bench.ai.openrouter.bodies(TRANSCRIPTIONS)
    assert again == started
    assert ran == list(STAGES[RunSource.IMPORT])
    assert RunState(run.state) is RunState.SUCCEEDED
    assert (meeting.title, meeting.source, meeting.seconds) == ("meeting", "import", VIDEO_SECONDS)
    assert meeting.ended_at is not None
    assert meeting.ended_at - meeting.started_at == timedelta(seconds=VIDEO_SECONDS)
    assert [(p["start_ms"], p["end_ms"]) for p in raw["parts"]] == [(0, run.audio_duration_ms)]
    assert lines == [(0, "Hello, team.", 0), (20_000, "Let us start.", 1)]
    assert (meeting.line_count, run.raw_transcript_key) == (2, raw_key(run.id))
    assert speakers == [(0, "numbered", 4_000), (1, "numbered", 6_000)]
    assert (body["input_audio"]["format"], body["response_format"]) == ("ogg", "verbose_json")
    assert body["provider"]["options"]["elevenlabs"]["diarize"] is True
    assert [tuple(row.values()) for row in costs] == [
        ("notes.transcribe", "transcribe", "ok", "audio_second")
    ]


async def test_voices_are_carried_across_a_cut_and_its_minutes_are_written_once(
    recording_bench: RecordingBench, video: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = uuid.uuid4()
    monkeypatch.setattr(recordings, "PART_MAX_MS", 5 * 60 * 1000)
    # Обе части слышат минуту за разрезом у 297 с: голоса узнаются по ней.
    # Части уходят разом: первая слышит 0–357 с, вторая 237–380 с — ответ по длине звука.
    first = scribe(
        (0.0, 4.0, 0, "Hello, team."), (20.0, 26.0, 1, "Let us start."),
        (240.0, 250.0, 0, "Next point."), (300.0, 310.0, 1, "Agreed."),
    )  # fmt: skip
    second = scribe(
        (3.0, 13.0, 5, "Next point."), (63.0, 73.0, 2, "Agreed."), (100.0, 105.0, 2, "Thanks."),
    )  # fmt: skip
    recording_bench.ai.openrouter.respond(TRANSCRIPTIONS, by_length(250.0, second, first))

    started = await imported(
        recording_bench, owner, await recording_bench.upload(owner, video, "video/mp4")
    )
    await recording_bench.drive()

    run, meeting = await run_and_meeting(recording_bench, owner, started)
    raw = await raw_of(recording_bench, run)
    lines, speakers = await lines_and_speakers(recording_bench, owner, meeting)
    cut = raw["parts"][1]["start_ms"]
    assert RunState(run.state) is RunState.SUCCEEDED
    assert abs(cut - 297_000) < 1_500
    assert [(p["start_ms"], p["end_ms"]) for p in raw["parts"]] == [
        (0, cut), (cut, run.audio_duration_ms),
    ]  # fmt: skip
    assert raw["parts"][1]["segments"][0]["start_ms"] == cut - 60_000 + 3_000
    assert [(text, speaker) for _, text, speaker in lines] == [
        ("Hello, team.", 0), ("Let us start.", 1), ("Next point.", 0), ("Agreed.", 1),
        ("Thanks.", 1),
    ]  # fmt: skip
    assert [(idx, role) for idx, role, _ in speakers] == [(0, "numbered"), (1, "numbered")]


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
        "/v1/notes/imports", json={"upload_id": str(theirs)}, headers=bearer((Home.EU, stranger))
    )
    refused = await recording_bench.http.post(
        "/v1/notes/imports",
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
