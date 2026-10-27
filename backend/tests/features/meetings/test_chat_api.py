"""The call's chat over its routes (meetings A6, MR-D11, §3.6)."""

import asyncio
import json
import uuid

import httpx

from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.meetings.infrastructure.room_records import RoomCallRecord
from tests.features.meetings.room_bench import NOW, RoomsBench


def code_of(answer: httpx.Response) -> str:
    """The error's code in the platform's envelope."""
    return str(answer.json()["error"]["code"])


async def call_with_two(bench: RoomsBench, *, live: bool = True) -> tuple[str, list[str]]:
    """A room with a live call and two guests in it: the room's id and their passes."""
    owner = uuid.uuid4()
    headers = {**bench.bearer(owner), "Idempotency-Key": uuid.uuid4().hex}
    room = (await bench.http.post("/v1/meetings/rooms", json={}, headers=headers)).json()
    token = str(room["link"]).rsplit("/", 1)[1]
    passes = [
        (await bench.http.post(f"/v1/meetings/join/{token}", json={"name": name})).json()[
            "room_pass"
        ]
        for name in ("Анна", "Ли")
    ]
    if live:
        async with bench.homes.transactions.begin(TenancyScope(Home.RU, owner)) as session:
            session.add(
                RoomCallRecord(
                    id=uuid.uuid4(), room_id=uuid.UUID(room["id"]), owner_id=owner,
                    lk_room_sid=f"RM_{uuid.uuid4().hex[:12]}", started_at=NOW, ceiling=4,
                )
            )  # fmt: skip
    return str(room["id"]), passes


async def send(
    bench: RoomsBench, room_id: str, room_pass: str, text: str, key: str
) -> httpx.Response:
    """A message sent with the pass and the key."""
    headers = {"X-Room-Pass": room_pass, "Idempotency-Key": key}
    return await bench.http.post(
        f"/v1/meetings/rooms/{room_id}/chat", json={"text": text}, headers=headers
    )


async def test_messages_are_kept_in_order_published_once_and_read_after_a_sequence(
    rooms_bench: RoomsBench,
) -> None:
    room_id, (anna, li) = await call_with_two(rooms_bench)

    first = await send(rooms_bench, room_id, anna, "  Привет  ", "k1")
    repeated = await send(rooms_bench, room_id, anna, "  Привет  ", "k1")
    second = await send(rooms_bench, room_id, li, "Ссылка: https://shosai.tech", "k2")
    missed = await rooms_bench.http.get(
        f"/v1/meetings/rooms/{room_id}/chat?after=1", headers={"X-Room-Pass": anna}
    )
    everything = await rooms_bench.http.get(
        f"/v1/meetings/rooms/{room_id}/chat?limit=1", headers={"X-Room-Pass": li}
    )

    assert (first.status_code, second.status_code) == (201, 201)
    assert repeated.json() == first.json()
    assert [
        (item["seq"], item["author"], item["text"]) for item in (first.json(), second.json())
    ] == [
        (1, "Анна", "Привет"),
        (2, "Ли", "Ссылка: https://shosai.tech"),
    ]
    assert [item["seq"] for item in missed.json()["items"]] == [2]
    assert (everything.json()["items"][0]["seq"], everything.json()["next_cursor"]) == (1, "1")
    packets = [json.loads(body) for _, topic, body in rooms_bench.sfu.published if topic == "chat"]
    assert [(packet["seq"], packet["id"]) for packet in packets] == [
        (1, first.json()["id"]),
        (2, second.json()["id"]),
    ]


async def test_a_message_needs_a_live_call_a_valid_pass_its_own_room_and_a_text(
    rooms_bench: RoomsBench,
) -> None:
    quiet_room, (quiet_pass, _) = await call_with_two(rooms_bench, live=False)
    room_id, (anna, _) = await call_with_two(rooms_bench)

    no_call = await send(rooms_bench, quiet_room, quiet_pass, "Есть кто?", "a")
    no_pass = await send(rooms_bench, room_id, "forged", "x", "b")
    wrong_room = await send(rooms_bench, room_id, quiet_pass, "x", "c")
    empty = await send(rooms_bench, room_id, anna, " \n ", "d")
    too_long = await send(rooms_bench, room_id, anna, "я" * 2_001, "e")

    assert (no_call.status_code, code_of(no_call)) == (409, "no_live_call")
    assert (no_pass.status_code, code_of(no_pass)) == (401, "room_pass_invalid")
    assert (wrong_room.status_code, code_of(wrong_room)) == (404, "room_not_found")
    assert (empty.status_code, code_of(empty)) == (422, "text_required")
    assert (too_long.status_code, code_of(too_long)) == (422, "text_too_long")


async def test_twenty_messages_per_ten_seconds_per_sender(rooms_bench: RoomsBench) -> None:
    room_id, (anna, li) = await call_with_two(rooms_bench)

    answers = await asyncio.gather(
        *(send(rooms_bench, room_id, anna, f"{index}", f"m{index}") for index in range(30))
    )
    other = await send(rooms_bench, room_id, li, "Я тоже", "li-1")

    # GCRA: двадцать разом, дальше — по одному в полсекунды; тридцать разом не проходят.
    accepted = [answer for answer in answers if answer.status_code == 201]
    refused = [answer for answer in answers if answer.status_code == 429]
    assert 20 <= len(accepted) < 30
    assert len(accepted) + len(refused) == 30
    assert code_of(refused[0]) == "rate_limited"
    # Звонок заперт на время выдачи номера: параллельные сообщения получают 1…n без пропусков.
    seqs = sorted(answer.json()["seq"] for answer in accepted)
    assert seqs == list(range(1, len(accepted) + 1))
    assert other.status_code == 201
