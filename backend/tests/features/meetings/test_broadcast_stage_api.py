"""The broadcast's stage, hands and chat over the link's routes (meetings A12b, MR-D7)."""

import uuid
from typing import Any

from shosai.features.meetings.domain.broadcasts import AUDIENCE, OFF_AIR, ON_STAGE
from tests.features.meetings.broadcast_bench import BroadcastBench
from tests.features.meetings.test_chat_api import code_of


async def live_broadcast(bench: BroadcastBench) -> tuple[str, dict[str, Any], dict[str, Any]]:
    """A broadcast on air with its host and one viewer: the token and their tickets."""
    host = uuid.uuid4()
    broadcast_id, token = await bench.create(host)
    stage = await bench.join(token, host)
    await bench.http.post(
        f"/v1/meetings/broadcasts/{broadcast_id}/start", headers=bench.bearer(host)
    )
    viewer = await bench.join(token, "Ли")
    room_name = stage["livekit_token"].split("|")[0]
    bench.sfu.seat(room_name, [stage["identity"], viewer["identity"]])
    return token, stage, viewer


async def test_a_raised_hand_invited_by_the_host_steps_onto_the_stage_with_its_rights(
    broadcast_bench: BroadcastBench,
) -> None:
    token, stage, viewer = await live_broadcast(broadcast_bench)
    host_pass, viewer_pass = stage["room_pass"], viewer["room_pass"]

    raised = await broadcast_bench.call("PUT", token, "/hand", viewer_pass, {"raised": True})
    hands = (await broadcast_bench.call("GET", token, "/state", host_pass)).json()["hands"]
    hidden = (await broadcast_bench.call("GET", token, "/state", viewer_pass)).json()
    early = await broadcast_bench.call("POST", token, "/stage", viewer_pass)
    principal = hands[0]["principal"]
    await broadcast_bench.call("POST", token, f"/hands/{principal}", host_pass, {"invite": True})
    invited = (await broadcast_bench.call("GET", token, "/state", viewer_pass)).json()["hand"]
    stepped = await broadcast_bench.call("POST", token, "/stage", viewer_pass)
    after = (await broadcast_bench.call("GET", token, "/state", viewer_pass)).json()

    assert raised.status_code == 204
    assert [(hand["name"], hand["invited"]) for hand in hands] == [("Ли", False)]
    assert (hidden["hands"], hidden["admissions"], hidden["hand"]) == ([], [], "raised")
    assert (early.status_code, code_of(early)) == (409, "not_invited")
    assert invited == "invited"
    assert stepped.status_code == 204
    assert broadcast_bench.sfu.grants[viewer["identity"]] == ON_STAGE
    assert (after["role"], after["hand"]) == ("speaker", "down")
    assert [(seat["name"], seat["role"]) for seat in after["members"]] == [
        ("Ведущая", "host"), ("Ли", "speaker"),
    ]  # fmt: skip


async def test_the_host_runs_the_stage_and_nobody_changes_the_host(
    broadcast_bench: BroadcastBench,
) -> None:
    token, stage, viewer = await live_broadcast(broadcast_bench)
    host_pass, viewer_pass = stage["room_pass"], viewer["room_pass"]
    await broadcast_bench.call("PUT", token, "/hand", viewer_pass, {"raised": True})
    principal = (await broadcast_bench.call("GET", token, "/state", host_pass)).json()["hands"][0][
        "principal"
    ]
    await broadcast_bench.call("POST", token, f"/hands/{principal}", host_pass, {"invite": True})
    await broadcast_bench.call("POST", token, "/stage", viewer_pass)
    host_principal = stage["identity"].split("__")[0]

    off_air = await broadcast_bench.call(
        "PATCH", token, f"/members/{principal}", host_pass, {"on_air": False}
    )
    off_grants = broadcast_bench.sfu.grants[viewer["identity"]]
    cohost = await broadcast_bench.call(
        "PATCH", token, f"/members/{principal}", host_pass, {"role": "cohost"}
    )
    against_host = await broadcast_bench.call(
        "PATCH", token, f"/members/{host_principal}", viewer_pass, {"on_air": False}
    )
    removed = await broadcast_bench.call("DELETE", token, f"/members/{principal}", host_pass)
    viewer_role = (await broadcast_bench.call("GET", token, "/state", viewer_pass)).json()["role"]

    assert (off_air.status_code, off_grants) == (204, OFF_AIR)
    assert cohost.status_code == 204
    assert (against_host.status_code, code_of(against_host)) == (403, "not_allowed")
    assert removed.status_code == 204
    assert broadcast_bench.sfu.grants[viewer["identity"]] == AUDIENCE
    assert viewer_role is None


async def test_the_audience_asks_in_the_chat_at_its_rate_and_the_stage_answers_marked(
    broadcast_bench: BroadcastBench,
) -> None:
    token, stage, viewer = await live_broadcast(broadcast_bench)

    asked = [
        await broadcast_bench.call(
            "POST", token, "/chat", viewer["room_pass"], {"text": f"Вопрос {n}"}
        )
        for n in range(6)
    ]
    answered = await broadcast_bench.call(
        "POST", token, "/chat", stage["room_pass"], {"text": "Отвечаю"}
    )
    page = (await broadcast_bench.call("GET", token, "/chat?after=4", viewer["room_pass"])).json()

    assert [answer.status_code for answer in asked] == [201] * 5 + [429]
    assert (answered.json()["from_stage"], answered.json()["seq"]) == (True, 6)
    assert [(item["seq"], item["from_stage"], item["mine"]) for item in page["items"]] == [
        (5, False, True), (6, True, False),
    ]  # fmt: skip
