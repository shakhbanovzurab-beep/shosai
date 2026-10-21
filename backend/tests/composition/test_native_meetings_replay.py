"""The shipped clients' meetings, replayed against the composed API app (notes step 21).

Each test sends the requests of macOS 1.4.5, Windows 1.4.5 and WhispererKit in their order,
with their headers and bodies (`contracts/draft/consumers.json` names the call sites), to
the app the `api` role builds, and decodes every answer the way the clients do
(`native_clients`). The live transcript goes over capture's socket, not served yet; no
worker runs here, so a recording waits for its intake. The app writes to the homes' buckets
outside the run's prefix, so each test deletes the objects its account's runs name.
"""

import uuid
from collections.abc import AsyncIterator, Mapping
from datetime import UTC, datetime
from typing import Final

import httpx
import pytest
import pytest_asyncio
from redis.asyncio import Redis
from shosai_contracts import (
    Candidate,
    CompatClass,
    Scope,
    check,
    load_baseline,
    parse_routes,
    render_text,
)
from shosai_contracts.jsonvalue import Json
from sqlalchemy import select

from shosai.composition.features import FEATURES
from shosai.core.config.roles import ProcessRole
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.notes.infrastructure.run_records import RunRecord
from tests.composition.native_clients import (
    decode_import_job,
    decode_meeting_detail,
    decode_meeting_note,
    decode_meeting_summary,
    decode_session_start,
    decode_token_response,
    decode_upload_state,
)
from tests.composition.public_routes import route_snapshot
from tests.composition.test_native_sign_in_replay import (
    DESKTOP,
    LOGIN,
    bearer,
    composed_api,
    connection,
)
from tests.composition.test_public_routes import SNAPSHOT, compose
from tests.harness.database_access import (
    DatabaseAccess,
    ProcessShape,
    open_database_access,
    slot_urls,
)
from tests.harness.run_slot import RunSlot
from tests.harness.settings import HarnessSettings
from tests.harness.shared_services import SlotBucket

# Маршруты S04 (встречи в нарезке черновика), которыми пользуются выпущенные клиенты.
NOTES_NATIVE: Final = Scope(
    slices=frozenset({"S04"}), classes=frozenset({CompatClass.NATIVE}), served_only=True
)
# Пункты «что сделать» ждут задач (MT-D4): единственный маршрут S04, который не обслужен.
ACTION_ITEMS: Final = "PATCH /v1/me/sessions/{session_id}/note/action-items/{item_id}"
AUDIO: Final = b"\x00\x00\x00\x18ftypM4A " + bytes(4096)
BOUNDARY: Final = "Boundary-3F2504E0-4F89-11D3-9A0C-0305E82C3301"
# Тело `APITransport.upload`: одно поле `file` с именем и типом файла.
FORM: Final = (
    (
        f"--{BOUNDARY}\r\n"
        'Content-Disposition: form-data; name="file"; filename="call.m4a"\r\n'
        "Content-Type: audio/mp4\r\n\r\n"
    ).encode()
    + AUDIO
    + f"\r\n--{BOUNDARY}--\r\n".encode()
)


def kit(meeting_id: uuid.UUID, *rest: str) -> str:
    """A WhispererKit path of the meeting: `uuidString` is upper case."""
    return "/".join([f"/v1/me/sessions/{str(meeting_id).upper()}", *rest])


type Desktop = tuple[httpx.AsyncClient, dict[str, str]]


@pytest_asyncio.fixture
async def desktop(
    run_slot: RunSlot,
    harness_settings: HarnessSettings,
    homes: DatabaseAccess,
    services: tuple[Redis, Redis, Mapping[Home, SlotBucket]],
) -> AsyncIterator[Desktop]:
    """The desktop's connection after its password sign-in, with its bearer header."""
    valkey, cache, buckets = services
    async with (
        composed_api(run_slot, harness_settings, (homes, valkey, cache)) as app,
        connection(app) as client,
    ):
        answer = await client.post("/v1/auth/login", json=LOGIN, headers=DESKTOP)
        headers = bearer(decode_token_response(answer.json()))
        try:
            yield client, headers
        finally:
            await forget_objects(run_slot, buckets[Home.RU])


@pytest.fixture
def services(
    valkey: Redis, redis_cache: Redis, buckets: Mapping[Home, SlotBucket]
) -> tuple[Redis, Redis, Mapping[Home, SlotBucket]]:
    """Valkey, the cache and the buckets the composed app reaches."""
    return valkey, redis_cache, buckets


async def forget_objects(run_slot: RunSlot, bucket: SlotBucket) -> None:
    """Delete the objects every run of the home names, and their unfinished uploads."""
    shape = ProcessShape(role=ProcessRole.WORKERS)
    async with (
        open_database_access(slot_urls(run_slot), shape) as workers,
        workers.transactions.begin(TenancyScope(Home.RU), read_only=True, sweep=True) as session,
    ):
        rows = (await session.execute(select(RunRecord.audio_key, RunRecord.multipart_id))).all()
    for key, upload in rows:
        if key is None:
            continue
        if upload is not None:
            await bucket.client.abort_multipart_upload(
                Bucket=bucket.bucket, Key=key, UploadId=upload
            )
        await bucket.client.delete_object(Bucket=bucket.bucket, Key=key)


async def started(client: httpx.AsyncClient, headers: dict[str, str], device: str) -> str:
    """`POST /v1/sessions` as both desktops send it; the id as the server wrote it."""
    answer = await client.post(
        "/v1/sessions", json={"title": "Weekly sync", "client_device_id": device}, headers=headers
    )
    assert answer.status_code < 300, answer.text
    return decode_session_start(answer.json())


async def ended(client: httpx.AsyncClient, headers: dict[str, str], meeting: str) -> int:
    """`PATCH /v1/sessions/{id}` as both desktops end a meeting: the time without a fraction."""
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    answer = await client.patch(
        f"/v1/sessions/{meeting}", json={"status": "completed", "ended_at": stamp}, headers=headers
    )
    return answer.status_code


async def uploaded(
    client: httpx.AsyncClient, headers: dict[str, str], meeting: str
) -> list[tuple[int, str, bool]]:
    """A recording in one part: begin, the part, the state, complete; each answer decoded."""
    base = f"/v1/me/sessions/{meeting.upper()}/audio"
    body = {"filename": "meeting.m4a", "mimetype": "audio/mp4", "client_build": "1.4.5"}
    begun = await client.post(f"{base}/init", json=body, headers=headers)
    run_id, _ = decode_upload_state(begun.json())
    part = {**headers, "Content-Type": "application/octet-stream"}
    answers = [
        begun,
        await client.put(f"{base}/{run_id}/part/1", content=AUDIO, headers=part),
        await client.get(f"{base}/{run_id}", headers=headers),
        await client.post(f"{base}/{run_id}/complete", headers=headers),
    ]
    return [(a.status_code, *decode_upload_state(a.json())) for a in answers]


async def test_a_macos_meeting_with_its_draft_and_its_recording(desktop: Desktop) -> None:
    client, headers = desktop
    meeting = await started(client, headers, "Annas-MacBook-Pro.local")
    draft = {"markdown": "- budget first", "client": "macos"}
    saved = await client.put(f"/v1/me/sessions/{meeting}/note/draft", json=draft, headers=headers)
    closed = await ended(client, headers, meeting)
    upload = await uploaded(client, headers, meeting)
    note = await client.get(f"/v1/me/sessions/{meeting}/note", headers=headers)
    listed = await client.get("/v1/me/sessions?limit=30&offset=0", headers=headers)

    assert saved.status_code < 300, saved.text
    assert closed == 200
    assert [(status, done) for status, _, done in upload] == [
        (200, False), (200, False), (200, False), (200, True),
    ]  # fmt: skip
    assert len({run for _, run, _ in upload}) == 1
    assert decode_meeting_note(note.json()) == "- budget first"
    assert [decode_meeting_summary(item) for item in listed.json()] == [uuid.UUID(meeting)]


async def test_a_windows_recording_discarded_and_begun_again(desktop: Desktop) -> None:
    client, headers = desktop
    meeting = await started(client, headers, "DESKTOP-7Q2M4K1")
    base = f"/v1/me/sessions/{meeting}/audio"
    body = {"filename": "meeting.wav", "mimetype": "audio/wav"}
    first, _ = decode_upload_state(
        (await client.post(f"{base}/init", json=body, headers=headers)).json()
    )
    discarded = await client.delete(f"{base}/{first}", headers=headers)
    closed = await ended(client, headers, meeting)
    upload = await uploaded(client, headers, meeting)
    note = await client.get(f"/v1/me/sessions/{meeting}/note", headers=headers)

    assert discarded.status_code < 300, discarded.text
    assert closed == 200
    assert upload[-1][0::2] == (200, True)
    assert decode_meeting_note(note.json()) == ""


async def test_the_kit_s_library_rename_import_and_deletion(desktop: Desktop) -> None:
    client, headers = desktop
    meeting = uuid.UUID(await started(client, headers, "Annas-MacBook-Pro.local"))
    detail = await client.get(kit(meeting, "full"), headers=headers)
    renamed = await client.patch(kit(meeting), json={"title": "Budget"}, headers=headers)
    multipart = {**headers, "Content-Type": f"multipart/form-data; boundary={BOUNDARY}"}
    accepted = await client.post("/v1/me/sessions/import", content=FORM, headers=multipart)
    job = await client.get(f"/v1/me/sessions/import/{accepted.json()['jobId']}", headers=headers)
    closed = await ended(client, headers, str(meeting))
    deleted = await client.delete(kit(meeting), headers=headers)
    listed = await client.get("/v1/me/sessions?limit=30&offset=0", headers=headers)

    assert decode_meeting_detail(detail.json()) == []
    # Как в черновике: id и название. `MeetingsClient.rename` кита ждёт `MeetingSummary`, но
    # из выпущенных сборок его не зовёт ни одна — macOS берёт у этого клиента только список.
    assert renamed.json() == {"id": str(meeting), "title": "Budget"}
    assert accepted.status_code < 300, accepted.text
    assert decode_import_job(job.json()) in {"uploading", "transcribing"}
    assert closed == 200
    assert deleted.status_code < 300, deleted.text
    assert meeting not in {decode_meeting_summary(item) for item in listed.json()}


async def test_the_gate_serves_every_native_notes_route_but_the_action_items(
    run_slot: RunSlot, harness_settings: HarnessSettings
) -> None:
    async with compose(run_slot, harness_settings, FEATURES) as apps:
        routes: list[Json] = [route for app in apps.values() for route in route_snapshot(app)]
        candidate = Candidate(
            openapi=apps["api"].openapi(), routes=parse_routes(routes, SNAPSHOT.name)
        )
        report = check(load_baseline(), candidate, NOTES_NATIVE)

    assert report.unserved == (ACTION_ITEMS,)
    assert report.is_compatible, render_text(report, NOTES_NATIVE)
