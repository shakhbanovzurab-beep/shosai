"""The native library and notes, in the shapes the 1.4.5 decoders read (step 12, MT-D1, MT-D12)."""

import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.identity.contracts import Principal
from shosai.features.meetings.infrastructure.meeting_records import MeetingRecord
from tests.features.billing.people_bench import bearer
from tests.features.meetings.native_bench import NativeBench, Written, meeting

type Json = dict[str, Any]
FIXTURES = Path(__file__).parents[4] / "parity" / "fixtures" / "meetings"
# Партиции расшифровки есть с текущего месяца: строки встреч пишутся в его начало.
START = datetime.now(UTC).replace(day=1, hour=1, minute=0, second=0, microsecond=0)
LINES = [(0, 0, "Hello, team."), (5_000, 1, "Let us start."), (12_000, 0, "Budget first.")]
SECTIONS: list[Json] = [
    {"kind": "summary", "heading_code": "summary", "text": "We agreed the budget."},
    {"kind": "key_points", "heading_code": "key_points", "finding_ids": [0]},
    {"kind": "action_items", "heading_code": "action_items", "finding_ids": [1]},
]
FINDINGS = [("key_point", "Budget is tight.", 6_000), ("action_item", "Send the estimate.", 13_000)]


def recorded(name: str, path: str) -> object:
    """A draft answer the parity harness recorded."""
    visit = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    body: object = next(ex["body"] for ex in visit["exchanges"] if ex["path"].endswith(path))
    return body


def differences(ours: object, theirs: object, at: str = "$") -> list[str]:
    """Where an answer of ours has a key or a JSON type the draft's answer did not."""
    if ours is None or theirs is None:
        return []
    if isinstance(theirs, dict):
        if not isinstance(ours, dict):
            return [at]
        return [
            found
            for key, value in theirs.items()
            for found in (
                [f"{at}.{key}"] if key not in ours else differences(ours[key], value, f"{at}.{key}")
            )
        ]
    if isinstance(theirs, list):
        if not isinstance(ours, list):
            return [at]
        return differences(ours[0], theirs[0], f"{at}[0]") if ours and theirs else []
    kinds = (bool, (int, float), str)
    return [] if any(isinstance(theirs, k) and isinstance(ours, k) for k in kinds) else [at]


async def answer(bench: NativeBench, owner: uuid.UUID, url: str) -> object:
    reply = await bench.http.get(url, headers=bearer((Home.EU, owner)))
    assert reply.status_code == 200, reply.text
    found: object = reply.json()
    return found


async def get(bench: NativeBench, owner: uuid.UUID, url: str) -> Json:
    found = await answer(bench, owner, url)
    assert isinstance(found, dict)
    return found


async def listed(bench: NativeBench, owner: uuid.UUID, url: str) -> list[Json]:
    found = await answer(bench, owner, url)
    assert isinstance(found, list)
    return found


async def test_the_answers_have_the_draft_s_keys_and_types(native_bench: NativeBench) -> None:
    owner = uuid.uuid4()
    written = Written(LINES, write_up=("enhanced", SECTIONS, FINDINGS))
    meeting_id = await meeting(native_bench, owner, ("Budget", START), written)

    rows = await listed(native_bench, owner, "/v1/me/sessions?limit=100&q=")
    full = await get(native_bench, owner, f"/v1/me/sessions/{meeting_id}/full")
    note = await get(native_bench, owner, f"/v1/me/sessions/{meeting_id}/note")

    assert differences(rows, recorded("library.en.json", "/v1/me/sessions")) == []
    assert differences(full, recorded("detail-budget.en.json", "/full")) == []
    assert differences(note, recorded("detail-budget.en.json", "/note")) == []
    assert [segment["id"] for segment in full["segments"]] == ["1", "2", "3"]


async def test_the_list_is_the_newest_two_hundred_that_match(native_bench: NativeBench) -> None:
    owner, stranger = uuid.uuid4(), uuid.uuid4()
    async with native_bench.homes.transactions.begin(TenancyScope(Home.EU, owner)) as session:
        session.add_all(
            MeetingRecord(
                id=uuid.uuid4(), user_id=owner, title=f"Sync {n}", status="completed",
                started_at=START + timedelta(hours=n),
                ended_at=START + timedelta(hours=n, minutes=30), seconds=1800,
            )
            for n in range(205)
        )  # fmt: skip
    special = await meeting(native_bench, owner, ("Q4: 100% plan", START - timedelta(days=1)))
    live = await meeting(
        native_bench, owner, ("Now", START + timedelta(days=30)), state=("active", True)
    )
    await meeting(native_bench, stranger, ("Not yours", START))

    first = await listed(native_bench, owner, "/v1/me/sessions?limit=200")
    past = await listed(native_bench, owner, "/v1/me/sessions?limit=50&offset=200")
    edge = await listed(native_bench, owner, "/v1/me/sessions?limit=50&offset=190")
    percent = await listed(native_bench, owner, "/v1/me/sessions?q=100%25")
    active = await listed(native_bench, owner, "/v1/me/sessions?status=active&limit=5")

    assert len(first) == 200
    assert first[0]["id"] == str(live)
    assert first[1]["title"] == "Sync 204"
    assert (past, len(edge)) == ([], 10)
    assert [row["id"] for row in percent] == [str(special)]
    assert [(row["id"], row["status"], row["ended_at"]) for row in active] == [
        (str(live), "active", None)
    ]
    assert first[1]["duration_ms"] == 1_800_000


async def test_a_voice_is_the_person_s_name_or_speaker_n_in_their_language(
    native_bench: NativeBench,
) -> None:
    owner = uuid.uuid4()
    native_bench.people.by_person[owner] = ("Мария", "ru")
    live = await meeting(native_bench, owner, ("Live", START), Written(LINES))
    recorded_roles = Written(LINES, roles=("numbered", "owner"))
    recording = await meeting(
        native_bench, owner, ("Recorded", START + timedelta(hours=1)), recorded_roles
    )

    by_live = await get(native_bench, owner, f"/v1/me/sessions/{live}/full")
    by_recording = await get(native_bench, owner, f"/v1/me/sessions/{recording}/full")

    assert [s["speaker"] for s in by_live["segments"]] == ["Мария", "Спикер 2", "Мария"]
    assert [s["speaker"] for s in by_recording["segments"]] == ["Спикер 1", "Мария", "Спикер 1"]


async def test_the_note_is_the_person_s_own_beside_leo_s_write_up(
    native_bench: NativeBench,
) -> None:
    owner = uuid.uuid4()
    native_bench.people.by_person[owner] = ("Мария", "ru")
    written = Written(LINES, write_up=("enhanced", SECTIONS, FINDINGS))
    meeting_id = await meeting(native_bench, owner, ("Budget", START), written)
    url = f"/v1/me/sessions/{meeting_id}/note"

    empty = await get(native_bench, owner, url)
    saved = await native_bench.http.put(
        f"{url}/draft", json={"markdown": "- my notes", "client": "macos", "extra": 1},
        headers=bearer((Home.EU, owner)),
    )  # fmt: skip
    again = await native_bench.http.put(
        f"{url}/draft", json={"markdown": "- my notes 2"}, headers=bearer((Home.EU, owner))
    )
    unknown = await native_bench.http.put(
        f"{url}/draft", json={"markdown": "x", "client": "ios"}, headers=bearer((Home.EU, owner))
    )

    assert (empty["draftMarkdown"], empty["version"], empty["lastAuthoringClient"]) == ("", 0, None)
    assert empty["enhancedMarkdown"] == (
        "## Сводка\nWe agreed the budget.\n\n## Ключевые моменты\n- Budget is tight.\n\n"
        "## Задачи из встречи\n- Send the estimate."
    )
    assert empty["actionItems"] == [
        {"id": empty["actionItems"][0]["id"], "text": "Send the estimate.", "done": False,
         "sourceSegmentId": "3"},
    ]  # fmt: skip
    assert empty["templateId"] is None
    assert (saved.json()["draftMarkdown"], saved.json()["version"]) == ("- my notes", 1)
    assert saved.json()["lastAuthoringClient"] == "macos"
    assert (again.json()["version"], again.json()["lastAuthoringClient"]) == (2, "web")
    assert (unknown.status_code, unknown.json()["detail"]) == (422, "note_client_unknown")


async def test_a_meeting_not_kept_stores_no_note_and_no_participant(
    native_bench: NativeBench,
) -> None:
    owner = uuid.uuid4()
    meeting_id = await meeting(native_bench, owner, ("Private", START), state=("active", False))
    headers = bearer((Home.EU, owner))

    native = await native_bench.http.put(
        f"/v1/me/sessions/{meeting_id}/note/draft", json={"markdown": "x"}, headers=headers
    )
    cabinet = await native_bench.http.put(
        f"/v1/meetings/{meeting_id}/my-notes", json={"text": "x"}, headers=headers
    )
    participant = await native_bench.http.post(
        f"/v1/meetings/{meeting_id}/participants",
        json={"email": "ann@example.com"},
        headers=headers,
    )
    note = await get(native_bench, owner, f"/v1/me/sessions/{meeting_id}/note")

    assert [(a.status_code, a.json()["detail"]) for a in (native, cabinet, participant)] == [
        (409, "private_meeting"),
    ] * 3
    assert (note["draftMarkdown"], note["version"]) == ("", 0)


async def test_the_setting_is_kept_and_mirrored_as_no_logs(native_bench: NativeBench) -> None:
    owner = uuid.uuid4()
    headers = bearer((Home.EU, owner))
    principal = Principal(owner, Home.EU, 0)

    before = await get(native_bench, owner, "/v1/meetings/settings")
    mirrored_before = await native_bench.settings.native_me(principal)
    put = await native_bench.http.put(
        "/v1/meetings/settings", json={"keep_meetings": False}, headers=headers
    )
    after = await get(native_bench, owner, "/v1/meetings/settings")
    mirrored_after = await native_bench.settings.native_me(principal)

    assert (before, put.json(), after) == (
        {"keep_meetings": True}, {"keep_meetings": False}, {"keep_meetings": False},
    )  # fmt: skip
    assert (mirrored_before, mirrored_after) == ({"no_logs": False}, {"no_logs": True})
