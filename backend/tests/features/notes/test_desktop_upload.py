"""The desktop recording's resumable upload, replayed as the shipped clients send it (step 11)."""

import os
import uuid

from sqlalchemy import update

from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.notes.application.run_rows import ensure_run
from shosai.features.notes.domain.recording_upload import PART_SIZE
from shosai.features.notes.domain.runs import RunSource, Stage, idempotency_key
from shosai.features.notes.domain.transcript_archive import archive_key
from shosai.features.notes.infrastructure.meeting_records import MeetingRecord
from shosai.features.notes.infrastructure.run_records import RunRecord
from tests.features.notes.desktop_upload import (
    MIB,
    audio,
    call,
    init,
    live_meeting,
    put_part,
)
from tests.features.notes.recording_bench import RecordingBench

FILE = os.urandom(11 * MIB)
PARTS = {1: FILE[:PART_SIZE], 2: FILE[PART_SIZE : 2 * PART_SIZE], 3: FILE[2 * PART_SIZE :]}


async def run_of(bench: RecordingBench, owner: uuid.UUID, run_id: str) -> RunRecord:
    async with bench.homes.transactions.begin(TenancyScope(Home.EU, owner)) as session:
        run = await session.get(RunRecord, uuid.UUID(run_id))
    assert run is not None
    return run


async def test_macos_resumes_out_of_order_and_repeated_parts_and_gets_its_receipt(
    recording_bench: RecordingBench,
) -> None:
    owner = uuid.uuid4()
    meeting = await live_meeting(recording_bench, owner)

    begun = (await init(recording_bench, owner, meeting, lead_ms=1_250)).json()
    ids = (meeting, begun["run_id"])
    second = await put_part(recording_bench, owner, ids, (2, PARTS[2]))
    first = await put_part(recording_bench, owner, ids, (1, PARTS[1]), stream=True)
    again = await put_part(recording_bench, owner, ids, (2, PARTS[2]))
    resumed = (await init(recording_bench, owner, meeting, lead_ms=1_250)).json()
    await put_part(recording_bench, owner, ids, (3, PARTS[3]))
    completed = await call(recording_bench, owner, "POST", audio(meeting, ids[1], "complete"))
    forgot = (await init(recording_bench, owner, meeting)).json()
    repeated = await call(recording_bench, owner, "POST", audio(meeting, ids[1], "complete"))

    run = await run_of(recording_bench, owner, ids[1])
    assert run.audio_key is not None
    stored = await recording_bench.storage[Home.EU].head(run.audio_key)
    assert (begun["part_size"], begun["received"], begun["completed"]) == (PART_SIZE, [], False)
    assert [second.json()["received"], first.json()["received"]] == [[2], [1, 2]]
    assert again.json()["bytes_received"] == 2 * PART_SIZE
    assert (resumed["run_id"], resumed["upload_id"], resumed["received"]) == (
        begun["run_id"], begun["upload_id"], [1, 2],
    )  # fmt: skip
    assert completed.status_code == 200
    assert completed.json() == {
        "run_id": ids[1], "upload_id": "", "part_size": PART_SIZE, "received": [],
        "bytes_received": len(FILE), "completed": True,
    }  # fmt: skip
    assert (forgot["completed"], forgot["bytes_received"]) == (True, len(FILE))
    assert repeated.json() == completed.json()
    assert stored is not None
    assert stored.size == len(FILE)
    assert (run.multipart_id, run.audio_lead_ms, run.audio_content_type) == (
        None, 1_250, "audio/mp4",
    )  # fmt: skip
    assert [p.stage for p in recording_bench.sent.payloads] == [Stage.INTAKE]


async def test_windows_discards_a_reservation_and_begins_again(
    recording_bench: RecordingBench,
) -> None:
    owner = uuid.uuid4()
    meeting = await live_meeting(recording_bench, owner)
    wav = ("meeting.wav", "audio/wav")
    mp3 = ("meeting.mp3", "audio/mpeg")

    reserved = (await init(recording_bench, owner, meeting, wav)).json()
    await put_part(recording_bench, owner, (meeting, reserved["run_id"]), (1, PARTS[1]))
    dropped = await call(recording_bench, owner, "DELETE", audio(meeting, reserved["run_id"]))
    fresh = (await init(recording_bench, owner, meeting, mp3)).json()
    ids = (meeting, fresh["run_id"])
    for number in (1, 2, 3):
        await put_part(recording_bench, owner, ids, (number, PARTS[number]))
    receipt = await call(recording_bench, owner, "POST", audio(meeting, ids[1], "complete"))
    gone = await call(recording_bench, owner, "DELETE", audio(meeting, str(uuid.uuid4())))

    run = await run_of(recording_bench, owner, ids[1])
    assert dropped.status_code == 204
    assert (fresh["run_id"], fresh["received"]) == (reserved["run_id"], [])
    assert fresh["upload_id"] != reserved["upload_id"]
    assert receipt.json()["bytes_received"] == len(FILE)
    assert run.audio_content_type == "audio/mpeg"
    assert gone.status_code == 404


async def test_each_refusal_keeps_the_draft_s_code(recording_bench: RecordingBench) -> None:
    owner, stranger = uuid.uuid4(), uuid.uuid4()
    meeting = await live_meeting(recording_bench, owner)
    private = await live_meeting(recording_bench, owner, state=("completed", False))
    archived = await live_meeting(recording_bench, owner)
    async with recording_bench.homes.transactions.begin(TenancyScope(Home.EU, owner)) as session:
        await session.execute(
            update(MeetingRecord)
            .where(MeetingRecord.id == archived)
            .values(transcript_archive_key=archive_key(archived), transcript_archive_lines=0)
        )
    run_id = (await init(recording_bench, owner, meeting)).json()["run_id"]
    ids = (meeting, run_id)

    answers = [
        await init(recording_bench, owner, private),
        await init(recording_bench, stranger, meeting),
        # Встреча с расшифровкой в архиве записи не берёт; клиенты бросают такую загрузку.
        await init(recording_bench, owner, archived),
        await put_part(recording_bench, owner, ids, (2001, b"x")),
        await put_part(recording_bench, owner, ids, (1, b"")),
        await put_part(recording_bench, owner, ids, (1, b"\0" * (10 * MIB + 1))),
        await call(recording_bench, owner, "POST", audio(meeting, run_id, "complete")),
        await put_part(recording_bench, stranger, ids, (1, b"x")),
    ]

    assert [(a.status_code, a.json()["detail"]) for a in answers] == [
        (409, "private_meeting"), (404, "meeting_not_found"), (404, "meeting_not_found"),
        (409, "bad_part"),
        (409, "empty_part"), (413, "part_too_large"), (409, "no_parts"),
        (404, "meeting_not_found"),
    ]  # fmt: skip


async def test_a_migrated_run_without_an_upload_answers_no_upload_until_init(
    recording_bench: RecordingBench,
) -> None:
    owner = uuid.uuid4()
    meeting_id = await live_meeting(recording_bench, owner)
    async with recording_bench.homes.transactions.begin(TenancyScope(Home.EU, owner)) as session:
        meeting = await session.get(MeetingRecord, meeting_id)
        assert meeting is not None
        key = idempotency_key(RunSource.RECORDING)
        run_id = str(await ensure_run(session, meeting, RunSource.RECORDING, key))
    ids = (meeting_id, run_id)

    part = await put_part(recording_bench, owner, ids, (1, b"x"))
    complete = await call(recording_bench, owner, "POST", audio(meeting_id, run_id, "complete"))
    state = await call(recording_bench, owner, "GET", audio(meeting_id, run_id))
    begun = (await init(recording_bench, owner, meeting_id)).json()

    assert [(a.status_code, a.json()["detail"]) for a in (part, complete)] == [
        (409, "no_upload"), (409, "no_upload"),
    ]  # fmt: skip
    assert (state.status_code, state.json()["completed"], state.json()["upload_id"]) == (
        200,
        False,
        "",
    )
    assert (begun["run_id"], begun["received"]) == (run_id, [])
    assert begun["upload_id"]
