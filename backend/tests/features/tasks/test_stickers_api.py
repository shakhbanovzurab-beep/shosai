"""Stickers and values answer as the cabinet's mocks do (tasks plan §3.15, mocks' route tests)."""

import uuid
from typing import Any

from tests.features.tasks.board_helpers import board, code_of, column_ids, made
from tests.features.tasks.task_bench import TaskBench


async def placed(
    bench: TaskBench, who: uuid.UUID, board_id: str, body: dict[str, Any]
) -> dict[str, Any]:
    """A sticker placed on the board."""
    answer = await bench.call(who, "POST", f"/v1/boards/{board_id}/stickers", body)
    assert answer.status_code == 201, answer.text
    return dict(answer.json())


async def on_board(bench: TaskBench, who: uuid.UUID) -> tuple[str, uuid.UUID]:
    """A board of the person with a task on its first column."""
    board_id = await made(bench, who)
    todo = column_ids(await board(bench, who, board_id))[0]
    task = await bench.task(who)
    await bench.place_in(who, task, (uuid.UUID(board_id), uuid.UUID(todo)))
    return board_id, task


TYPE = {
    "kind": "states", "name": "Тип",
    "states": [{"name": "Фича", "color": "blue"}, {"name": "Баг", "color": "red"}],
}  # fmt: skip


async def test_values_are_the_tasks_and_stay_with_it_off_the_board(task_bench: TaskBench) -> None:
    me = uuid.uuid4()
    board_id, task = await on_board(task_bench, me)
    estimate = await placed(task_bench, me, board_id, {"kind": "number", "name": "Оценка"})
    path = f"/v1/tasks/{task}/values/{estimate['id']}"

    put = await task_bench.call(me, "PUT", path, {"number": 2.5})
    card = (await board(task_bench, me, board_id))["columns"][0]["cards"][0]
    shown = (await task_bench.call(me, "GET", f"/v1/tasks/{task}")).json()
    removed = await task_bench.call(
        me, "DELETE", f"/v1/boards/{board_id}/stickers/{estimate['id']}"
    )
    after = (await task_bench.call(me, "GET", f"/v1/tasks/{task}")).json()

    assert put.json() == {"number": 2.5}
    assert card["values"] == {estimate["id"]: {"number": 2.5}}
    assert shown["values"] == {estimate["id"]: {"number": 2.5}}
    assert removed.status_code == 204
    assert after["values"] == {}
    assert [(v["sticker"]["id"], v["value"]) for v in after["other_values"]] == [
        (estimate["id"], {"number": 2.5})
    ]


async def test_a_value_of_another_kind_or_out_of_bounds_is_refused(task_bench: TaskBench) -> None:
    me = uuid.uuid4()
    board_id, task = await on_board(task_bench, me)
    estimate = await placed(task_bench, me, board_id, {"kind": "number", "name": "Оценка"})
    kind = await placed(task_bench, me, board_id, TYPE)
    other = await placed(task_bench, me, board_id, {**TYPE, "name": "Другой"})
    path = f"/v1/tasks/{task}/values"

    refusals = [
        await task_bench.call(
            me, "PUT", f"{path}/{estimate['id']}", {"state_id": kind["states"][0]["id"]}
        ),
        await task_bench.call(me, "PUT", f"{path}/{estimate['id']}", {"number": 0.001}),
        await task_bench.call(me, "PUT", f"{path}/{estimate['id']}", {"number": 10**12}),
        await task_bench.call(
            me, "PUT", f"{path}/{kind['id']}", {"state_id": other["states"][0]["id"]}
        ),
        await task_bench.call(me, "PUT", f"{path}/{uuid.uuid4()}", {"text": "Нет"}),
        await task_bench.call(uuid.uuid4(), "PUT", f"{path}/{kind['id']}", {"text": "Чужое"}),
    ]

    assert [(a.status_code, code_of(a)) for a in refusals] == [
        (422, "value_kind_mismatch"), (422, "validation_error"), (422, "validation_error"),
        (404, "state_not_found"), (404, "sticker_not_found"), (404, "task_not_found"),
    ]  # fmt: skip


async def test_usage_counts_values_and_a_removed_state_clears_exactly_its_values(
    task_bench: TaskBench,
) -> None:
    me = uuid.uuid4()
    board_id, first = await on_board(task_bench, me)
    second, third = await task_bench.task(me), await task_bench.task(me)
    kind = await placed(task_bench, me, board_id, TYPE)
    feature, bug = (state["id"] for state in kind["states"])
    for task, state in ((first, feature), (second, feature), (third, bug)):
        await task_bench.call(
            me, "PUT", f"/v1/tasks/{task}/values/{kind['id']}", {"state_id": state}
        )

    async def usage() -> dict[str, Any]:
        items = (await task_bench.call(me, "GET", "/v1/stickers")).json()["items"]
        return dict(next(item["usage"] for item in items if item["id"] == kind["id"]))

    before = await usage()
    changed = await task_bench.call(
        me, "PATCH", f"/v1/stickers/{kind['id']}",
        {"name": "Вид", "states": [
            {"id": feature, "name": "Фича", "color": "teal"}, {"name": "Идея", "color": "amber"},
        ]},
    )  # fmt: skip
    after = await usage()
    unknown = await task_bench.call(
        me,
        "PATCH",
        f"/v1/stickers/{kind['id']}",
        {"states": [{"id": str(uuid.uuid4()), "name": "А", "color": "red"}]},
    )
    third_values = (await task_bench.call(me, "GET", f"/v1/tasks/{third}")).json()

    assert before == {"tasks": 3, "states": {feature: 2, bug: 1}}
    assert (changed.json()["name"], [s["name"] for s in changed.json()["states"]]) == (
        "Вид",
        ["Фича", "Идея"],
    )
    assert changed.json()["owner"] == {"user_id": str(me)}
    assert after == {"tasks": 2, "states": {feature: 2}}
    assert (unknown.status_code, code_of(unknown)) == (404, "state_not_found")
    assert third_values["values"] == {}


async def test_a_sticker_is_reused_on_another_board_and_deleted_everywhere(
    task_bench: TaskBench,
) -> None:
    me = uuid.uuid4()
    board_id, task = await on_board(task_bench, me)
    other_board = await made(task_bench, me)
    kind = await placed(task_bench, me, board_id, TYPE)
    await task_bench.call(
        me, "PUT", f"/v1/tasks/{task}/values/{kind['id']}", {"state_id": kind["states"][1]["id"]}
    )

    again = await placed(task_bench, me, other_board, {"sticker_id": kind["id"]})
    listed = (await task_bench.call(me, "GET", "/v1/stickers")).json()["items"]
    foreign = await task_bench.call(uuid.uuid4(), "DELETE", f"/v1/stickers/{kind['id']}")
    deleted = await task_bench.call(me, "DELETE", f"/v1/stickers/{kind['id']}")
    detail = (await task_bench.call(me, "GET", f"/v1/tasks/{task}")).json()
    stickers = (await board(task_bench, me, board_id))["stickers"]

    assert (again["id"], again["visible"]) == (kind["id"], True)
    assert {b["id"] for b in listed[0]["boards"]} == {board_id, other_board}
    assert (foreign.status_code, code_of(foreign)) == (404, "sticker_not_found")
    assert deleted.status_code == 204
    assert (detail["values"], detail["other_values"]) == ({}, [])
    assert [s["id"] for s in stickers][-1] == "time_tracking"


async def test_a_board_shows_hides_and_keeps_its_stickers_in_order(task_bench: TaskBench) -> None:
    me = uuid.uuid4()
    board_id, _ = await on_board(task_bench, me)
    estimate = await placed(task_bench, me, board_id, {"kind": "number", "name": "Оценка"})
    note = await placed(task_bench, me, board_id, {"kind": "text", "name": "Заметка"})
    path = f"/v1/boards/{board_id}/stickers"
    automations = {"start_on_arrival": True, "restart_on_move": False, "stop_on_done": True}

    hidden = await task_bench.call(me, "PATCH", f"{path}/{estimate['id']}", {"visible": False})
    due = await task_bench.call(me, "PATCH", f"{path}/due", {"visible": False})
    stopwatch = await task_bench.call(
        me, "PATCH", f"{path}/stopwatch", {"visible": True, "automations": automations}
    )
    wrong = await task_bench.call(me, "PATCH", f"{path}/due", {"automations": automations})
    empty = await task_bench.call(me, "PATCH", f"{path}/due", {})
    system = await task_bench.call(me, "DELETE", f"{path}/priority")
    missing = await task_bench.call(me, "DELETE", f"{path}/{uuid.uuid4()}")
    detail = await board(task_bench, me, board_id)

    assert hidden.json() | {"states": None} == {
        "id": estimate["id"], "kind": "number", "name": "Оценка", "states": None,
        "owner": {"user_id": str(me)}, "visible": False,
    }  # fmt: skip
    assert (due.json()["id"], due.json()["visible"]) == ("due", False)
    assert stopwatch.json()["automations"] == automations
    assert [(a.status_code, code_of(a)) for a in (wrong, empty, system, missing)] == [
        (422, "validation_error"), (422, "validation_error"), (409, "system_sticker"),
        (404, "sticker_not_on_board"),
    ]  # fmt: skip
    ids = [s["id"] for s in detail["stickers"]]
    assert ids == [
        "assignee", "due", "priority", "recurrence", "stopwatch", "timer", "time_tracking",
        estimate["id"], note["id"],
    ]  # fmt: skip
    assert [s["visible"] for s in detail["stickers"]][:2] == [True, False]
    assert detail["stickers"][4]["automations"] == automations


async def test_a_card_copy_takes_its_values(task_bench: TaskBench) -> None:
    me = uuid.uuid4()
    board_id, task = await on_board(task_bench, me)
    todo = column_ids(await board(task_bench, me, board_id))[0]
    note = await placed(task_bench, me, board_id, {"kind": "text", "name": "Заметка"})
    await task_bench.call(me, "PUT", f"/v1/tasks/{task}/values/{note['id']}", {"text": "  Срочно "})

    copy = await task_bench.call(
        me, "POST", f"/v1/boards/{board_id}/cards",
        {"title": "Копия", "column_id": todo, "position": 0, "copy_of": str(task)},
    )  # fmt: skip

    assert copy.json()["values"] == {note["id"]: {"text": "Срочно"}}
