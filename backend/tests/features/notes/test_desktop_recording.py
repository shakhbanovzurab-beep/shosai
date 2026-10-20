"""A desktop recording's run (step 11, MT-D3): minutes once, live lines replaced, notes kept."""

import asyncio
import uuid
from datetime import timedelta
from pathlib import Path

import httpx
import pytest
from prometheus_client import CollectorRegistry
from sqlalchemy import select

from shosai.core.ai.calls import ModelRef, ModelRoute, Provider
from shosai.core.config.roles import ProcessRole
from shosai.core.events.catalog import EventTypes
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.notes.application.notes_model import NotesModel
from shosai.features.notes.application.pipeline import StageWork
from shosai.features.notes.application.run_recovery import RunRecovery
from shosai.features.notes.application.run_rows import progress_of
from shosai.features.notes.application.write_up_stage import WriteUpStage
from shosai.features.notes.domain.runs import RunSource, RunState, Stage, StageStatus
from shosai.features.notes.infrastructure.meeting_records import (
    MeetingRecord,
    SpeakerRecord,
    TranscriptLineRecord,
)
from shosai.features.notes.infrastructure.notes_metrics import NotesMetrics
from shosai.features.notes.infrastructure.notes_records import NotesRecord
from shosai.features.notes.infrastructure.own_notes_records import OwnNotesRecord
from shosai.features.notes.infrastructure.pipeline_metrics import PipelineMetrics
from shosai.features.notes.infrastructure.run_records import RunRecord
from shosai.features.notes.module import NOTES
from tests.features.notes.desktop_upload import audio, call, init, live_meeting, put_part
from tests.features.notes.recording_bench import RecordingBench, ffmpeg
from tests.features.notes.test_imports import TRANSCRIPTIONS
from tests.harness.database_access import ProcessShape, open_database_access, slot_urls
from tests.harness.run_slot import RunSlot

ME, THEM = 0, 1
LIVE = [(4_000, 5_000, ME, "Live me."), (21_000, 8_000, THEM, "Live them.")]


@pytest.fixture(scope="session")
def call_recording(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """150 seconds of AAC in an m4a, as macOS compresses a meeting."""
    target = tmp_path_factory.mktemp("desktop") / "meeting.m4a"
    ffmpeg(
        "-f", "lavfi", "-i", "sine=frequency=300:sample_rate=16000", "-t", "150",
        "-ac", "1", "-c:a", "aac", "-b:a", "32k", str(target),
    )  # fmt: skip
    return target


async def uploaded(
    bench: RecordingBench, owner: uuid.UUID, meeting: uuid.UUID, recording: Path
) -> uuid.UUID:
    """The recording sent in one part and completed; its run."""
    run_id = (await init(bench, owner, meeting, lead_ms=0)).json()["run_id"]
    body = await asyncio.to_thread(recording.read_bytes)
    await put_part(bench, owner, (meeting, run_id), (1, body))
    receipt = await call(bench, owner, "POST", audio(meeting, run_id, "complete"))
    assert receipt.json()["completed"]
    return uuid.UUID(run_id)


def recognised() -> httpx.Response:
    segments = [
        {"start": 4.0, "end": 9.0, "text": "Recorded me."},
        {"start": 21.0, "end": 29.0, "text": "Recorded them."},
    ]
    return httpx.Response(
        200, json={"text": "", "segments": segments, "usage": {"seconds": 150.0, "cost": 0.001}}
    )


async def state_of(
    bench: RecordingBench, owner: uuid.UUID, meeting_id: uuid.UUID, run_id: uuid.UUID
) -> tuple[MeetingRecord, RunRecord, list[tuple[int, int | None, str, str]], list[str]]:
    async with bench.homes.transactions.begin(TenancyScope(Home.EU, owner)) as session:
        meeting = await session.get(MeetingRecord, meeting_id)
        run = await session.get(RunRecord, run_id)
        rows = await session.execute(
            select(
                TranscriptLineRecord.start_ms, TranscriptLineRecord.speaker_idx,
                TranscriptLineRecord.origin, TranscriptLineRecord.text,
            )
            .where(TranscriptLineRecord.session_id == meeting_id)
            .order_by(TranscriptLineRecord.start_ms)
        )  # fmt: skip
        roles = await session.scalars(
            select(SpeakerRecord.role)
            .where(SpeakerRecord.session_id == meeting_id)
            .order_by(SpeakerRecord.idx)
        )
        lines = [(start, speaker, origin, text) for start, speaker, origin, text in rows]
        found = (meeting, run, lines, list(roles))
    assert meeting is not None
    assert run is not None
    return meeting, run, found[2], found[3]


async def test_a_longer_recording_counts_once_replaces_the_live_lines_and_finds_the_owner(
    recording_bench: RecordingBench, call_recording: Path
) -> None:
    owner = uuid.uuid4()
    meeting_id = await live_meeting(recording_bench, owner, seconds=60, lines=LIVE)
    async with recording_bench.homes.transactions.begin(TenancyScope(Home.EU, owner)) as session:
        session.add(OwnNotesRecord(id=uuid.uuid4(), session_id=meeting_id, user_id=owner,
                                   markdown="My own words.", version=3, client="macos",
                                   updated_at=recording_bench.clock.now))  # fmt: skip
    recording_bench.ai.openrouter.answer(TRANSCRIPTIONS, recognised())
    recording_bench.ai.pyannote.turns = [
        {"speaker": "SPEAKER_05", "start": 3.5, "end": 10.0},
        {"speaker": "SPEAKER_02", "start": 20.0, "end": 30.0},
    ]

    run_id = await uploaded(recording_bench, owner, meeting_id, call_recording)
    ran = await recording_bench.drive()

    meeting, run, lines, roles = await state_of(recording_bench, owner, meeting_id, run_id)
    async with recording_bench.homes.transactions.begin(TenancyScope(Home.EU, owner)) as session:
        own = await session.scalar(select(OwnNotesRecord.markdown).where(
            OwnNotesRecord.session_id == meeting_id))  # fmt: skip
    assert ran == [Stage.INTAKE, Stage.TRANSCRIBE, Stage.DIARIZE, Stage.ALIGN,
                   Stage.FINDINGS, Stage.WRITE_UP]  # fmt: skip
    assert RunState(run.state) is RunState.SUCCEEDED
    assert meeting.seconds == 150
    assert lines == [
        (4_000, 0, "recording", "Recorded me."),
        (21_000, 1, "recording", "Recorded them."),
    ]
    assert roles == ["owner", "numbered"]
    assert (meeting.latest_run_id, own) == (run_id, "My own words.")


async def test_a_recording_adding_more_than_the_minutes_left_is_not_processed(
    recording_bench: RecordingBench, call_recording: Path
) -> None:
    owner = uuid.uuid4()
    async with recording_bench.homes.transactions.begin(TenancyScope(Home.EU, owner)) as session:
        await recording_bench.minutes.meeting_deleted(
            session, owner, (uuid.uuid4(), recording_bench.clock.now), 119 * 60
        )
    meeting_id = await live_meeting(recording_bench, owner, seconds=60, lines=LIVE)

    run_id = await uploaded(recording_bench, owner, meeting_id, call_recording)
    await recording_bench.drive()

    meeting, run, lines, _ = await state_of(recording_bench, owner, meeting_id, run_id)
    intake = progress_of(run.stage_state)[Stage.INTAKE]
    assert (intake.status, intake.error_code) == (StageStatus.FAILED, "upload_exceeds_minutes")
    assert meeting.seconds == 60
    assert [text for *_, text in lines] == ["Live me.", "Live them."]
    assert recording_bench.ai.openrouter.requests == []


async def test_a_write_up_the_person_chose_is_left_as_it_was(
    recording_bench: RecordingBench,
) -> None:
    owner, chosen = uuid.uuid4(), uuid.uuid4()
    meeting_id = await live_meeting(recording_bench, owner, seconds=60, lines=LIVE)
    async with recording_bench.homes.transactions.begin(TenancyScope(Home.EU, owner)) as session:
        session.add(NotesRecord(session_id=meeting_id, user_id=owner, write_up={"sections": []},
                                write_up_template="oneOnOne", write_up_run_id=chosen,
                                write_up_automatic=False))  # fmt: skip
    model = NotesModel(
        recording_bench.ai.providers,
        ModelRoute(ModelRef(Provider.OPENROUTER, "probe/notes")),
        NotesMetrics(CollectorRegistry()),
    )
    stage = WriteUpStage(
        recording_bench.homes.transactions,
        (PortDirectory(), EventOutbox(EventTypes(NOTES.events)), model),
        10_000,
    )
    scope = TenancyScope(Home.EU, owner)

    await stage.run(
        StageWork(scope, uuid.uuid4(), meeting_id, RunSource.RECORDING, Stage.WRITE_UP, 1)
    )

    async with recording_bench.homes.transactions.begin(scope) as session:
        notes = await session.get(NotesRecord, meeting_id)
    assert notes is not None
    assert (notes.write_up_run_id, notes.write_up_template) == (chosen, "oneOnOne")
    assert recording_bench.ai.openrouter.requests == []


async def test_a_recording_waits_while_its_meeting_goes_on_and_starts_once_it_ends(
    recording_bench: RecordingBench, call_recording: Path, run_slot: RunSlot
) -> None:
    owner = uuid.uuid4()
    meeting_id = await live_meeting(recording_bench, owner, state=("active", True))
    later = recording_bench.clock.now + timedelta(minutes=5)
    shape = ProcessShape(role=ProcessRole.WORKERS)

    await uploaded(recording_bench, owner, meeting_id, call_recording)
    async with open_database_access(slot_urls(run_slot), shape) as workers:
        recovery = RunRecovery(
            workers.transactions,
            (recording_bench.engine, PipelineMetrics(CollectorRegistry())),
            lambda: later,
        )
        while_live = await recovery.run(Home.EU)
        async with recording_bench.homes.transactions.begin(
            TenancyScope(Home.EU, owner)
        ) as session:
            meeting = await session.get(MeetingRecord, meeting_id)
            assert meeting is not None
            meeting.status, meeting.ended_at = "completed", recording_bench.clock.now
        after_end = await recovery.run(Home.EU)

    assert (while_live, after_end) == (0, 1)
    assert [p.stage for p in recording_bench.sent.payloads] == [Stage.INTAKE]
