"""The native import: the draft's refusals, the streamed body and the job (step 9b)."""

import asyncio
import uuid
from collections.abc import AsyncIterator, MutableMapping
from pathlib import Path
from typing import Any

import httpx

from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.notes.channels.http.native_import_texts import FAILURE_TEXTS
from shosai.features.notes.domain.native_import import IMPORT_MAX_BYTES
from shosai.features.notes.domain.runs import STAGES, RunSource
from shosai.features.notes.infrastructure.meeting_records import MeetingRecord
from shosai.features.notes.infrastructure.notes_records import SettingsRecord
from shosai.features.notes.infrastructure.run_records import RunRecord
from tests.features.billing.people_bench import bearer
from tests.features.notes.recording_bench import RecordingBench
from tests.features.notes.test_imports import TRANSCRIPTIONS, heard

BOUNDARY = "shosai-probe-boundary"
CHUNK = 64 * 1024
type Json = dict[str, Any]


async def sent_body(name: str, data: bytes | Path, kind: str) -> AsyncIterator[bytes]:
    """A multipart body with the field `file`, sent in chunks without a length."""
    yield (
        f'--{BOUNDARY}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\n'
        f"Content-Type: {kind}\r\n\r\n"
    ).encode()
    body = data if isinstance(data, bytes) else await asyncio.to_thread(data.read_bytes)
    for start in range(0, len(body), CHUNK):
        yield body[start : start + CHUNK]
    yield f"\r\n--{BOUNDARY}--\r\n".encode()


async def import_file(
    bench: RecordingBench, owner: uuid.UUID, file: tuple[str, bytes | Path, str]
) -> httpx.Response:
    """The native import of a file, streamed as the clients send it."""
    return await bench.http.post(
        "/v1/me/sessions/import",
        content=sent_body(*file),
        headers={
            **bearer((Home.EU, owner)),
            "Content-Type": f"multipart/form-data; boundary={BOUNDARY}",
        },
    )


async def job(bench: RecordingBench, owner: uuid.UUID, job_id: str) -> httpx.Response:
    return await bench.http.get(
        f"/v1/me/sessions/import/{job_id}", headers=bearer((Home.EU, owner))
    )


async def left_behind(bench: RecordingBench, people: list[uuid.UUID]) -> tuple[int, int, int]:
    """Meetings and runs of the people, and objects under the import's prefix."""
    found = [0, 0]
    for person in people:
        async with bench.homes.transactions.begin(TenancyScope(Home.EU, person)) as session:
            found[0] += len((await session.scalars(MeetingRecord.__table__.select())).all())
            found[1] += len((await session.scalars(RunRecord.__table__.select())).all())
    objects = [info async for info in bench.storage[Home.EU].list_objects("transient/import/")]
    return found[0], found[1], len(objects)


async def test_each_refusal_answers_in_the_draft_s_order_and_leaves_nothing(
    recording_bench: RecordingBench,
) -> None:
    private, spent, plain = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    async with recording_bench.homes.transactions.begin(TenancyScope(Home.EU, private)) as session:
        session.add(SettingsRecord(user_id=private, keep_meetings=False))
    async with recording_bench.homes.transactions.begin(TenancyScope(Home.EU, spent)) as session:
        await recording_bench.minutes.meeting_deleted(
            session, spent, (uuid.uuid4(), recording_bench.clock.now), 120 * 60
        )
    cases = [
        (private, ("notes.txt", b"", "text/plain")),
        (spent, ("notes.txt", b"", "text/plain")),
        (plain, ("notes.txt", b"words", "text/plain")),
        (plain, ("empty.m4a", b"", "audio/mp4")),
        (plain, ("big.m4a", b"\0" * (IMPORT_MAX_BYTES + 1), "audio/mp4")),
    ]

    answers = [await import_file(recording_bench, person, file) for person, file in cases]

    assert [(a.status_code, a.json()["detail"]) for a in answers] == [
        (422, "import_unavailable_no_logs"), (402, "minutes_exhausted"),
        (422, "unsupported_audio_format"), (422, "empty_file"), (413, "file_too_large"),
    ]  # fmt: skip
    assert all(a.json()["error"]["code"] == a.json()["detail"] for a in answers)
    assert await left_behind(recording_bench, [private, spent, plain]) == (0, 0, 0)
    assert recording_bench.sent.payloads == []


async def test_a_streamed_recording_becomes_a_job_the_clients_poll_to_its_transcript(
    recording_bench: RecordingBench, video: Path
) -> None:
    owner, stranger = uuid.uuid4(), uuid.uuid4()
    recording_bench.ai.openrouter.answer(TRANSCRIPTIONS, heard())

    accepted = await import_file(recording_bench, owner, ("meeting.mp4", video, "audio/mp4"))
    job_id = accepted.json()["jobId"]
    waiting = await job(recording_bench, owner, job_id)
    ran = await recording_bench.drive()
    transcribed = await job(recording_bench, owner, job_id)
    foreign = await job(recording_bench, stranger, job_id)
    unknown = await job(recording_bench, owner, str(uuid.uuid4()))

    async with recording_bench.homes.transactions.begin(TenancyScope(Home.EU, owner)) as session:
        run = await session.get(RunRecord, uuid.UUID(job_id))
        assert run is not None
        meeting = await session.get(MeetingRecord, run.session_id)
    assert meeting is not None
    assert run.audio_key is not None
    stored = await recording_bench.storage[Home.EU].head(run.audio_key)
    assert accepted.status_code == 202
    assert list(accepted.json()) == ["jobId"]
    assert waiting.json() == {
        "id": job_id, "fileName": "meeting.mp4", "stage": "uploading", "progress": 0.0,
        "meetingId": str(meeting.id), "error": None,
    }  # fmt: skip
    assert ran == list(STAGES[RunSource.IMPORT])
    assert (transcribed.json()["stage"], transcribed.json()["progress"]) == ("ready", 1.0)
    assert (meeting.title, meeting.source, meeting.line_count) == ("meeting", "import", 2)
    assert run.audio_key.startswith("transient/import/")
    assert stored is not None
    assert stored.size == (await asyncio.to_thread(video.stat)).st_size
    assert (foreign.status_code, foreign.json()["detail"]) == (404, "import_job_not_found")
    assert unknown.status_code == 404


async def test_a_failed_import_says_why_in_the_person_s_language(
    recording_bench: RecordingBench, video: Path
) -> None:
    owner = uuid.uuid4()
    recording_bench.languages.by_person[owner] = "ru"
    async with recording_bench.homes.transactions.begin(TenancyScope(Home.EU, owner)) as session:
        await recording_bench.minutes.meeting_deleted(
            session, owner, (uuid.uuid4(), recording_bench.clock.now), 115 * 60
        )

    accepted = await import_file(recording_bench, owner, ("call.mp4", video, "audio/mp4"))
    await recording_bench.drive()
    failed = await job(recording_bench, owner, accepted.json()["jobId"])

    body: Json = failed.json()
    assert (body["stage"], body["fileName"]) == ("failed", "call.mp4")
    assert body["error"] == FAILURE_TEXTS["ru"]["upload_exceeds_minutes"]
    assert recording_bench.ai.openrouter.requests == []


async def test_a_body_without_the_file_field_is_refused_and_ten_a_minute_are_taken(
    recording_bench: RecordingBench,
) -> None:
    owner = uuid.uuid4()
    headers = bearer((Home.EU, owner))

    plain = await recording_bench.http.post(
        "/v1/me/sessions/import", json={"file": "x"}, headers=headers
    )
    fields = await recording_bench.http.post(
        "/v1/me/sessions/import", data={"note": "x"}, files={"other": ("a.m4a", b"1")},
        headers=headers,
    )  # fmt: skip
    rest = [
        await import_file(recording_bench, owner, ("notes.txt", b"1", "text/plain"))
        for _ in range(9)
    ]

    assert [plain.status_code, fields.status_code] == [422, 422]
    assert {answer.status_code for answer in rest[:-1]} == {422}
    assert (rest[-1].status_code, rest[-1].json()["error"]["code"]) == (429, "rate_limited")
    assert await left_behind(recording_bench, [owner]) == (0, 0, 0)


async def test_a_client_gone_mid_body_leaves_no_object_and_no_rows(
    recording_bench: RecordingBench,
) -> None:
    owner = uuid.uuid4()
    head = (
        f'--{BOUNDARY}\r\nContent-Disposition: form-data; name="file"; filename="call.m4a"'
        "\r\nContent-Type: audio/mp4\r\n\r\n"
    ).encode()
    arriving: list[Json] = [
        {"type": "http.request", "body": head, "more_body": True},
        *({"type": "http.request", "body": b"\0" * CHUNK, "more_body": True} for _ in range(100)),
        {"type": "http.disconnect"},
    ]
    headers = [
        (b"host", b"testserver"),
        (b"authorization", bearer((Home.EU, owner))["Authorization"].encode()),
        (b"content-type", f"multipart/form-data; boundary={BOUNDARY}".encode()),
    ]
    scope: Json = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "POST",
        "scheme": "http", "path": "/v1/me/sessions/import", "raw_path": b"/v1/me/sessions/import",
        "query_string": b"", "root_path": "", "headers": headers,
        "client": ("127.0.0.1", 50000), "server": ("testserver", 80),
    }  # fmt: skip
    answered: list[Json] = []

    async def receive() -> Json:
        return arriving.pop(0) if arriving else {"type": "http.disconnect"}

    async def send(message: MutableMapping[str, Any]) -> None:
        answered.append(dict(message))

    await recording_bench.app(scope, receive, send)

    [start] = [m for m in answered if m["type"] == "http.response.start"]
    assert start["status"] == 400
    assert await left_behind(recording_bench, [owner]) == (0, 0, 0)
    assert recording_bench.sent.payloads == []
