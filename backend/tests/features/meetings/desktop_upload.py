"""A live meeting of the person's and the desktop clients' upload calls, for step 11's tests.

The calls go to the routes the way the shipped clients send them: the meeting's id in upper
case as macOS writes it, `audio_lead_ms` when the client measured it, raw part bodies with
their length, or chunked when a client sends none.
"""

import uuid
from collections.abc import AsyncIterator, Sequence
from datetime import timedelta
from typing import Any

import httpx

from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.meetings.infrastructure.meeting_records import (
    MeetingRecord,
    TranscriptLineRecord,
)
from tests.features.billing.people_bench import bearer
from tests.features.meetings.recording_bench import RecordingBench

type Json = dict[str, Any]
MIB = 1024 * 1024


async def live_meeting(
    bench: RecordingBench,
    owner: uuid.UUID,
    *,
    seconds: int = 600,
    state: tuple[str, bool] = ("completed", True),
    lines: Sequence[tuple[int, int, int, str]] = (),
) -> uuid.UUID:
    """A live meeting of the person's: its status, whether it is kept, its live lines."""
    status, kept = state
    started = bench.clock.now - timedelta(hours=1)
    async with bench.homes.transactions.begin(TenancyScope(Home.EU, owner)) as session:
        meeting = MeetingRecord(
            id=uuid.uuid4(), user_id=owner, title="Weekly sync", status=status, source="live",
            started_at=started, seconds=seconds, kept=kept, line_count=len(lines),
            ended_at=None if status == "active" else started + timedelta(seconds=seconds),
        )  # fmt: skip
        session.add(meeting)
        await session.flush()
        session.add_all(
            TranscriptLineRecord(
                session_id=meeting.id, seq=seq, meeting_started_at=started,
                started_at=started + timedelta(milliseconds=start), start_ms=start,
                duration_ms=duration, speaker_idx=speaker, text=text, origin="live",
            )
            for seq, (start, duration, speaker, text) in enumerate(lines, 1)
        )  # fmt: skip
    return meeting.id


def audio(meeting_id: uuid.UUID, *rest: str) -> str:
    """An upload route of the meeting, its id upper-cased as macOS sends it."""
    return "/".join([f"/v1/me/sessions/{str(meeting_id).upper()}/audio", *rest])


async def init(
    bench: RecordingBench,
    owner: uuid.UUID,
    meeting_id: uuid.UUID,
    file: tuple[str, str] = ("meeting.m4a", "audio/mp4"),
    lead_ms: int | None = None,
) -> httpx.Response:
    """`init` with the file's name and type, and the lead when it was measured."""
    body: Json = {"filename": file[0], "mimetype": file[1], "client_build": "1.4.5"}
    if lead_ms is not None:
        body["audio_lead_ms"] = lead_ms
    return await bench.http.post(
        audio(meeting_id, "init"), json=body, headers=bearer((Home.EU, owner))
    )


async def chunked(body: bytes) -> AsyncIterator[bytes]:
    """The body in 64 KiB chunks, sent without a length."""
    for start in range(0, len(body), 64 * 1024):
        yield body[start : start + 64 * 1024]


async def put_part(
    bench: RecordingBench,
    owner: uuid.UUID,
    ids: tuple[uuid.UUID, str],
    part: tuple[int, bytes],
    *,
    stream: bool = False,
) -> httpx.Response:
    """One part's raw body, with its length or chunked."""
    meeting_id, run_id = ids
    number, body = part
    return await bench.http.put(
        audio(meeting_id, run_id, "part", str(number)),
        content=chunked(body) if stream else body,
        headers={**bearer((Home.EU, owner)), "Content-Type": "application/octet-stream"},
    )


async def call(bench: RecordingBench, owner: uuid.UUID, method: str, url: str) -> httpx.Response:
    """A body-less call of the upload routes."""
    return await bench.http.request(method, url, headers=bearer((Home.EU, owner)))
