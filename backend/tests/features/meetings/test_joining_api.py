"""Joining a room by its link and renewing a room pass (meetings A4, §3.6)."""

import json
import uuid

import httpx
import pytest
from sqlalchemy import update

from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.meetings.infrastructure.room_records import RoomBanRecord, RoomRecord
from tests.features.meetings.room_bench import NOW, PLATFORM_CEILING, RoomsBench

GUEST = {"name": "Гость", "device": {"os": "linux", "client": "web", "browser": "Firefox 140"}}


def code_of(answer: httpx.Response) -> str:
    """The error's code in the platform's envelope."""
    return str(answer.json()["error"]["code"])


async def open_room(bench: RoomsBench, owner: uuid.UUID) -> tuple[uuid.UUID, str]:
    """A room of the owner: its id and its invitation token."""
    headers = {**bench.bearer(owner), "Idempotency-Key": uuid.uuid4().hex}
    room = (await bench.http.post("/v1/meetings/rooms", json={}, headers=headers)).json()
    return uuid.UUID(room["id"]), str(room["link"]).rsplit("/", 1)[1]


async def join(
    bench: RoomsBench, token: str, body: object = GUEST, person: uuid.UUID | None = None
) -> httpx.Response:
    """The join as a guest, or as the person when given."""
    headers = {} if person is None else dict(bench.bearer(person))
    return await bench.http.post(f"/v1/meetings/join/{token}", json=body, headers=headers)


async def test_a_guest_joins_directly_and_the_first_join_creates_the_sfu_room(
    rooms_bench: RoomsBench,
) -> None:
    owner = uuid.uuid4()
    room_id, token = await open_room(rooms_bench, owner)
    rooms_bench.people.room_participants = 3

    answer = await join(rooms_bench, token)

    assert answer.status_code == 200, answer.text
    body = answer.json()
    assert (body["role"], body["ceiling"], body["room_id"]) == ("participant", 3, None)
    assert body["room"] == {"title": None, "notes_on": True, "recording": False}
    assert body["identity"].startswith("guest-")
    held = next(iter(rooms_bench.sfu.rooms_held.values()))
    assert held.max_participants == 3
    assert json.loads(held.metadata)["marks"] == {"notes": True, "recording": False}
    room_name, identity = body["livekit_token"].split("|")
    assert (room_name, identity) == (held.name, body["identity"])
    assert body["room_pass"]
    assert room_id.version == 7


@pytest.mark.parametrize(
    ("plan", "ceiling"), [(None, PLATFORM_CEILING), (3, 3), (100, PLATFORM_CEILING), (1, 2)]
)
async def test_the_ceiling_is_the_owners_plan_capped_by_the_platform(
    rooms_bench: RoomsBench, plan: int | None, ceiling: int
) -> None:
    _, token = await open_room(rooms_bench, uuid.uuid4())
    rooms_bench.people.room_participants = plan

    assert (await join(rooms_bench, token)).json()["ceiling"] == ceiling


async def test_the_owner_joins_under_their_name_on_two_devices(rooms_bench: RoomsBench) -> None:
    owner = uuid.uuid4()
    rooms_bench.people.named[owner] = "Анна"
    room_id, token = await open_room(rooms_bench, owner)

    phone = (await join(rooms_bench, token, {"name": "ignored"}, owner)).json()
    laptop = (await join(rooms_bench, token, {}, owner)).json()

    assert (phone["role"], phone["room_id"]) == ("owner", str(room_id))
    assert phone["identity"] != laptop["identity"]
    assert phone["identity"].split("__")[0] == laptop["identity"].split("__")[0] == str(owner)


async def test_refusals_follow_the_domains_order(rooms_bench: RoomsBench) -> None:
    owner, person = uuid.uuid4(), uuid.uuid4()
    rooms_bench.people.named[person] = "Пётр"
    room_id, token = await open_room(rooms_bench, owner)
    scope = TenancyScope(Home.RU, owner)

    unknown = await join(rooms_bench, "nosuchtoken00")
    malformed = await join(rooms_bench, "!")
    nameless = await join(rooms_bench, token, {})
    async with rooms_bench.homes.transactions.begin(scope) as session:
        session.add(
            RoomBanRecord(
                id=uuid.uuid4(), room_id=room_id, owner_id=owner, principal=str(person),
                banned_by=str(owner),
            )
        )  # fmt: skip
    removed = await join(rooms_bench, token, {}, person)
    rooms_bench.people.room_participants = 2
    await join(rooms_bench, token)
    name = next(iter(rooms_bench.sfu.rooms_held))
    rooms_bench.sfu.seat(name, ["guest-0123456789ab__0a1b2c3d", "guest-0123456789ac__0a1b2c3d"])
    full = await join(rooms_bench, token)
    async with rooms_bench.homes.transactions.begin(scope) as session:
        await session.execute(
            update(RoomRecord).values(state="closed", closed_at=NOW, closed_by="owner")
        )
    finished = await join(rooms_bench, token)
    async with rooms_bench.homes.transactions.begin(scope) as session:
        await session.execute(update(RoomRecord).values(closed_by="account"))
    hidden = await join(rooms_bench, token)

    assert [(answer.status_code, code_of(answer)) for answer in (unknown, malformed)] == [
        (404, "not_found"),
        (404, "not_found"),
    ]
    assert (nameless.status_code, code_of(nameless)) == (422, "name_required")
    assert (removed.status_code, code_of(removed)) == (403, "removed")
    assert (full.status_code, code_of(full)) == (409, "room_full")
    assert (finished.status_code, code_of(finished)) == (410, "room_finished")
    assert (hidden.status_code, code_of(hidden)) == (404, "not_found")


async def test_an_sfu_that_does_not_answer_is_video_unavailable(rooms_bench: RoomsBench) -> None:
    _, token = await open_room(rooms_bench, uuid.uuid4())
    rooms_bench.sfu.up = False

    answer = await join(rooms_bench, token)

    assert (answer.status_code, code_of(answer)) == (503, "video_unavailable")


async def test_a_room_pass_renews_while_the_room_is_open_and_not_after(
    rooms_bench: RoomsBench,
) -> None:
    owner = uuid.uuid4()
    room_id, token = await open_room(rooms_bench, owner)
    first = (await join(rooms_bench, token)).json()["room_pass"]
    refresh = "/v1/meetings/passes/refresh"

    renewed = await rooms_bench.http.post(refresh, headers={"X-Room-Pass": first})
    reused = await rooms_bench.http.post(refresh, headers={"X-Room-Pass": first})
    missing = await rooms_bench.http.post(refresh)
    await rooms_bench.http.post(
        f"/v1/meetings/rooms/{room_id}/end", headers=rooms_bench.bearer(owner)
    )
    after_end = await rooms_bench.http.post(
        refresh, headers={"X-Room-Pass": renewed.json()["room_pass"]}
    )

    assert renewed.status_code == 200
    assert renewed.json()["room_pass"] != first
    assert [(answer.status_code, code_of(answer)) for answer in (reused, missing)] == [
        (401, "room_pass_invalid"),
        (401, "room_pass_invalid"),
    ]
    assert (after_end.status_code, code_of(after_end)) == (410, "room_finished")


async def test_ten_joins_a_minute_per_address(rooms_bench: RoomsBench) -> None:
    _, token = await open_room(rooms_bench, uuid.uuid4())

    answers = [await join(rooms_bench, token) for _ in range(11)]

    assert [answer.status_code for answer in answers[:10]] == [200] * 10
    assert (answers[10].status_code, code_of(answers[10])) == (429, "rate_limited")
