"""Broadcasts by their link: the host's lifecycle, who gets in and with which rights, the
waiting room, bans and the 100 viewers (meetings A12b, MR-D7)."""

import json
import uuid

from sqlalchemy import select

from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.meetings.domain.broadcasts import AUDIENCE, ON_STAGE, VIEWERS_MAX
from shosai.features.meetings.infrastructure.stream_records import StreamBanRecord, StreamRecord
from tests.features.meetings.broadcast_bench import BroadcastBench
from tests.features.meetings.test_chat_api import code_of
from tests.harness.database_access import DatabaseAccess


async def test_a_paid_host_creates_a_broadcast_once_and_a_free_one_does_not(
    broadcast_bench: BroadcastBench,
) -> None:
    host, key = uuid.uuid4(), uuid.uuid4().hex
    broadcast_bench.people.named[host] = "Ведущая"
    headers = {**broadcast_bench.bearer(host), "Idempotency-Key": key}
    body = {"title": "  Обзор релиза  ", "waiting_room": True}

    first = await broadcast_bench.http.post("/v1/meetings/broadcasts", json=body, headers=headers)
    again = await broadcast_bench.http.post("/v1/meetings/broadcasts", json=body, headers=headers)
    broadcast_bench.people.paid = False
    free = await broadcast_bench.http.post(
        "/v1/meetings/broadcasts",
        json=body,
        headers={**headers, "Idempotency-Key": uuid.uuid4().hex},
    )

    made = first.json()
    assert (first.status_code, made["title"], made["state"], made["waiting_room"]) == (
        201, "Обзор релиза", "scheduled", True,
    )  # fmt: skip
    assert made["link"].startswith("https://shosai.tech/live/")
    assert again.json()["id"] == made["id"]
    assert (free.status_code, code_of(free)) == (403, "broadcast_not_in_plan")


async def test_the_stage_gets_in_before_the_start_and_the_audience_only_live_and_hidden(
    broadcast_bench: BroadcastBench,
) -> None:
    host = uuid.uuid4()
    broadcast_id, token = await broadcast_bench.create(host)

    stage = await broadcast_bench.join(token, host)
    early = await broadcast_bench.join(token, "Ли")
    started = await broadcast_bench.http.post(
        f"/v1/meetings/broadcasts/{broadcast_id}/start", headers=broadcast_bench.bearer(host)
    )
    viewer = await broadcast_bench.join(token, "Ли")
    as_call = await broadcast_bench.http.post(f"/v1/meetings/join/{token}", json={"name": "Ли"})

    assert (stage["entry"], stage["role"], stage["broadcast_id"]) == ("stage", "host", broadcast_id)
    assert broadcast_bench.sfu.grants[stage["identity"]] == ON_STAGE
    assert (early["entry"], early["room_pass"], early["livekit_token"]) == ("not_live", None, None)
    assert started.json()["state"] == "live"
    assert (viewer["entry"], viewer["role"], viewer["broadcast_id"]) == ("audience", None, None)
    assert broadcast_bench.sfu.grants[viewer["identity"]] == AUDIENCE
    assert AUDIENCE.hidden
    assert not AUDIENCE.can_publish_data
    # Ссылка трансляции не открывает её комнату как обычный звонок.
    assert (as_call.status_code, code_of(as_call)) == (404, "not_found")


async def test_the_waiting_room_lets_a_viewer_in_only_when_the_host_admits(
    broadcast_bench: BroadcastBench,
) -> None:
    host = uuid.uuid4()
    broadcast_id, token = await broadcast_bench.create(host, waiting_room=True)
    stage = await broadcast_bench.join(token, host)
    await broadcast_bench.http.post(
        f"/v1/meetings/broadcasts/{broadcast_id}/start", headers=broadcast_bench.bearer(host)
    )

    waiting = await broadcast_bench.join(token, "Ли")
    knock = {"knock": waiting["knock"]}
    still = await broadcast_bench.http.post(f"/v1/meetings/live/{token}/knock", json=knock)
    queue = (await broadcast_bench.call("GET", token, "/state", stage["room_pass"])).json()
    admitted = await broadcast_bench.call(
        "POST", token, f"/admissions/{waiting['knock']}", stage["room_pass"], {"admitted": True}
    )
    inside = await broadcast_bench.http.post(f"/v1/meetings/live/{token}/knock", json=knock)
    turned = await broadcast_bench.join(token, "Ким")
    await broadcast_bench.call(
        "POST", token, f"/admissions/{turned['knock']}", stage["room_pass"], {"admitted": False}
    )
    away = await broadcast_bench.http.post(
        f"/v1/meetings/live/{token}/knock", json={"knock": turned["knock"]}
    )

    assert (waiting["entry"], still.json()["entry"]) == ("wait", "wait")
    room_name = stage["livekit_token"].split("|")[0]
    assert (room_name, "stream", b'{"v": 1, "kind": "state"}') in broadcast_bench.sfu.published
    assert [item["name"] for item in queue["admissions"]] == ["Ли"]
    assert admitted.status_code == 204
    assert (inside.json()["entry"], inside.json()["room_pass"] is not None) == ("audience", True)
    assert (away.status_code, code_of(away)) == (403, "removed")


async def test_a_banned_viewer_is_refused_and_a_full_broadcast_turns_the_next_one_away(
    broadcast_bench: BroadcastBench, homes: DatabaseAccess
) -> None:
    host = uuid.uuid4()
    broadcast_id, token = await broadcast_bench.create(host)
    stage = await broadcast_bench.join(token, host)
    await broadcast_bench.http.post(
        f"/v1/meetings/broadcasts/{broadcast_id}/start", headers=broadcast_bench.bearer(host)
    )
    room_name = stage["livekit_token"].split("|")[0]
    viewers = [f"guest-{index:012x}__0a1b2c3d" for index in range(VIEWERS_MAX)]
    broadcast_bench.sfu.seat(room_name, [stage["identity"], *viewers])

    full = await broadcast_bench.join(token, "Сто первый")
    banned_one = uuid.uuid4()
    async with homes.transactions.begin(TenancyScope(Home.RU, host)) as session:
        stream = (await session.scalars(select(StreamRecord))).one()
        session.add(
            StreamBanRecord(
                id=uuid.uuid4(), stream_id=stream.id, owner_id=host, principal=str(banned_one),
                banned_by=str(host),
            )
        )  # fmt: skip
    broadcast_bench.people.named[banned_one] = "Удалённый"
    banned = await broadcast_bench.http.post(
        f"/v1/meetings/live/{token}/join", json={}, headers=broadcast_bench.bearer(banned_one)
    )

    assert full["entry"] == "full"
    assert (banned.status_code, code_of(banned)) == (403, "removed")


async def test_the_end_tells_the_room_closes_everything_and_the_link_answers_ended(
    broadcast_bench: BroadcastBench,
) -> None:
    host = uuid.uuid4()
    broadcast_id, token = await broadcast_bench.create(host)
    stage = await broadcast_bench.join(token, host)
    owner = broadcast_bench.bearer(host)
    await broadcast_bench.http.post(f"/v1/meetings/broadcasts/{broadcast_id}/start", headers=owner)

    ended = await broadcast_bench.http.post(
        f"/v1/meetings/broadcasts/{broadcast_id}/end", headers=owner
    )
    again = await broadcast_bench.http.post(
        f"/v1/meetings/broadcasts/{broadcast_id}/start", headers=owner
    )
    after = await broadcast_bench.http.post(f"/v1/meetings/live/{token}/join", json={"name": "Ли"})

    room_name = stage["livekit_token"].split("|")[0]
    pushed = [
        json.loads(payload)
        for room, topic, payload in broadcast_bench.sfu.published
        if room == room_name and topic == "stream"
    ]
    assert ended.json()["state"] == "ended"
    assert {"v": 1, "kind": "ended"} in pushed
    assert room_name in broadcast_bench.sfu.deleted
    assert (again.status_code, code_of(again)) == (409, "broadcast_ended")
    # Ссылка закончившейся трансляции отвечает её концом, а не ошибкой.
    assert after.json()["entry"] == "ended"
