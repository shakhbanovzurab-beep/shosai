"""The owner's rooms on `/v1/meetings/rooms` (meetings A4, §3.6)."""

import json
import uuid

import httpx

from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.meetings.application.video_server import RoomSpec
from shosai.features.meetings.infrastructure.room_records import RoomCallRecord, RoomRecord
from tests.features.meetings.room_bench import NOW, RoomsBench

KEY = {"Idempotency-Key": "new-meeting-1"}


def code_of(answer: httpx.Response) -> str:
    """The error's code in the platform's envelope."""
    return str(answer.json()["error"]["code"])


async def open_room(bench: RoomsBench, person: uuid.UUID, **body: object) -> dict[str, object]:
    """A room opened through the route."""
    headers = {**bench.bearer(person), "Idempotency-Key": uuid.uuid4().hex}
    answer = await bench.http.post("/v1/meetings/rooms", json=body, headers=headers)
    assert answer.status_code == 201, answer.text
    room: dict[str, object] = answer.json()
    return room


async def start_call(bench: RoomsBench, person: uuid.UUID, room: dict[str, object]) -> None:
    """A live call of the room, as the webhook will write it, and its SFU room."""
    room_id = uuid.UUID(str(room["id"]))
    org = room["workspace_id"]
    space = None if org is None else uuid.UUID(str(org))
    async with bench.homes.transactions.begin(TenancyScope(Home.RU, person, space)) as session:
        record = await session.get(RoomRecord, room_id)
        assert record is not None
        session.add(
            RoomCallRecord(
                id=uuid.uuid4(), room_id=room_id, owner_id=person, org_id=space,
                lk_room_sid=f"RM_{uuid.uuid4().hex[:12]}", started_at=NOW, ceiling=4,
            )
        )  # fmt: skip
        lk_name = record.lk_room_name
    await bench.sfu.create_room(RoomSpec(lk_name, 4, "{}"))
    bench.sfu.seat(lk_name, ["guest-0123456789ab__0a1b2c3d", "guest-0123456789ab__0a1b2c3e"])


async def test_new_meeting_opens_a_room_once_per_key_with_its_link(rooms_bench: RoomsBench) -> None:
    person = uuid.uuid4()
    headers = {**rooms_bench.bearer(person), **KEY}
    first = await rooms_bench.http.post(
        "/v1/meetings/rooms", json={"title": "  Планёрка "}, headers=headers
    )
    again = await rooms_bench.http.post(
        "/v1/meetings/rooms", json={"title": "  Планёрка "}, headers=headers
    )
    other = await rooms_bench.http.post(
        "/v1/meetings/rooms", json={"title": "Другое"}, headers=headers
    )

    assert (first.status_code, again.status_code) == (201, 201)
    room = first.json()
    assert again.json()["id"] == room["id"]
    assert other.status_code == 422
    assert code_of(other) == "idempotency_key_reused"
    assert (room["title"], room["state"], room["notes_on"], room["call"]) == (
        "Планёрка",
        "open",
        True,
        None,
    )
    token = str(room["link"]).removeprefix("https://shosai.tech/meet/")
    assert len(token) == 12


async def test_a_workspace_room_needs_membership(rooms_bench: RoomsBench) -> None:
    person, org = uuid.uuid4(), uuid.uuid4()
    outside = await rooms_bench.http.post(
        "/v1/meetings/rooms", json={"workspace_id": str(org)},
        headers={**rooms_bench.bearer(person), **KEY},
    )  # fmt: skip
    assert (outside.status_code, code_of(outside)) == (404, "workspace_not_found")

    rooms_bench.spaces.of[person] = {org}
    room = await open_room(rooms_bench, person, workspace_id=str(org))
    assert room["workspace_id"] == str(org)


async def test_only_the_owner_reads_and_changes_a_room(rooms_bench: RoomsBench) -> None:
    owner, stranger = uuid.uuid4(), uuid.uuid4()
    room = await open_room(rooms_bench, owner)
    path = f"/v1/meetings/rooms/{room['id']}"

    stranger_headers = rooms_bench.bearer(stranger)
    read = await rooms_bench.http.get(path, headers=stranger_headers)
    changed = await rooms_bench.http.patch(path, json={"title": "x"}, headers=stranger_headers)
    for answer in (read, changed):
        assert (answer.status_code, code_of(answer)) == (404, "room_not_found")
    ended = await rooms_bench.http.post(f"{path}/end", headers=rooms_bench.bearer(stranger))
    assert ended.status_code == 404

    renamed = await rooms_bench.http.patch(
        path, json={"title": " Ретро "}, headers=rooms_bench.bearer(owner)
    )
    cleared = await rooms_bench.http.patch(
        path, json={"title": "", "notes_on": False}, headers=rooms_bench.bearer(owner)
    )
    assert renamed.json()["title"] == "Ретро"
    assert (cleared.json()["title"], cleared.json()["notes_on"]) == (None, False)


async def test_ending_closes_for_good_even_when_the_sfu_does_not_answer(
    rooms_bench: RoomsBench,
) -> None:
    owner = uuid.uuid4()
    room = await open_room(rooms_bench, owner)
    path = f"/v1/meetings/rooms/{room['id']}"
    rooms_bench.sfu.up = False

    ended = await rooms_bench.http.post(f"{path}/end", headers=rooms_bench.bearer(owner))
    rooms_bench.sfu.up = True
    again = await rooms_bench.http.post(f"{path}/end", headers=rooms_bench.bearer(owner))
    changed = await rooms_bench.http.patch(
        path, json={"title": "Снова"}, headers=rooms_bench.bearer(owner)
    )

    assert (ended.status_code, ended.json()["state"]) == (200, "closed")
    assert again.json()["closed_at"] == ended.json()["closed_at"]
    assert len(rooms_bench.sfu.deleted) == 1
    assert (changed.status_code, code_of(changed)) == (409, "room_closed")


async def test_live_lists_the_owners_calls_in_the_space_with_their_counts(
    rooms_bench: RoomsBench,
) -> None:
    owner, stranger, org = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    rooms_bench.spaces.of[owner] = {org}
    quiet = await open_room(rooms_bench, owner)
    personal = await open_room(rooms_bench, owner, title="Личная")
    workspace = await open_room(rooms_bench, owner, workspace_id=str(org))
    await start_call(rooms_bench, owner, personal)
    await start_call(rooms_bench, owner, workspace)

    mine = await rooms_bench.http.get(
        "/v1/meetings/rooms?state=live", headers=rooms_bench.bearer(owner)
    )
    theirs = await rooms_bench.http.get("/v1/meetings/rooms", headers=rooms_bench.bearer(stranger))
    in_space = await rooms_bench.http.get(
        f"/v1/meetings/rooms?workspace_id={org}", headers=rooms_bench.bearer(owner)
    )

    assert [item["id"] for item in mine.json()["items"]] == [personal["id"]]
    assert mine.json()["items"][0]["call"] == {
        "started_at": NOW.isoformat().replace("+00:00", "Z"),
        "participants": 2,
    }
    assert str(quiet["id"]) not in json.dumps(mine.json())
    assert theirs.json() == {"items": [], "next_cursor": None}
    assert [item["id"] for item in in_space.json()["items"]] == [workspace["id"]]


async def test_switching_notes_in_a_live_call_changes_the_mark_first(
    rooms_bench: RoomsBench,
) -> None:
    owner = uuid.uuid4()
    room = await open_room(rooms_bench, owner)
    await start_call(rooms_bench, owner, room)
    path = f"/v1/meetings/rooms/{room['id']}"
    rooms_bench.sfu.up = False

    refused = await rooms_bench.http.patch(
        path, json={"notes_on": False}, headers=rooms_bench.bearer(owner)
    )
    rooms_bench.sfu.up = True
    unchanged = await rooms_bench.http.get(path, headers=rooms_bench.bearer(owner))
    switched = await rooms_bench.http.patch(
        path, json={"notes_on": False}, headers=rooms_bench.bearer(owner)
    )

    assert (refused.status_code, code_of(refused)) == (503, "video_unavailable")
    assert unchanged.json()["notes_on"] is True
    assert switched.json()["notes_on"] is False
    marks = [json.loads(value)["marks"] for value in rooms_bench.sfu.metadata.values()]
    assert {"notes": False, "recording": False} in marks
