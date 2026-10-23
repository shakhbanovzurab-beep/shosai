"""A board's columns and cards answer as the cabinet's mocks do (tasks plan §3.14)."""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

from shosai.features.tasks.domain.recurrence import Every, Recurrence, recurrence_json
from tests.features.tasks.board_helpers import board, cards_of, code_of, column_ids, made
from tests.features.tasks.task_bench import TaskBench


async def test_columns_are_added_recoloured_collapsed_and_removed_without_losing_a_card(
    task_bench: TaskBench,
) -> None:
    me = uuid.uuid4()
    board_id = await made(task_bench, me, "project")
    path = f"/v1/boards/{board_id}/columns"
    created = await task_bench.call(
        me, "POST", path, {"title": "QA", "kind": "in_progress", "position": 1, "color": "teal"}
    )
    columns = column_ids(await board(task_bench, me, board_id))
    backlog, todo = uuid.UUID(columns[0]), uuid.UUID(columns[2])
    ideas = [await task_bench.task(me), await task_bench.task(me)]
    for task in ideas:
        await task_bench.place_in(me, task, (uuid.UUID(board_id), backlog))
    planned = await task_bench.task(me)
    await task_bench.place_in(me, planned, (uuid.UUID(board_id), todo))

    collapsed = await task_bench.call(
        me, "PATCH", f"{path}/{created.json()['id']}", {"collapsed": True, "color": None}
    )
    removed = await task_bench.call(me, "DELETE", f"{path}/{backlog}")
    after = await board(task_bench, me, board_id)
    done_column = after["columns"][-1]["id"]
    last = await task_bench.call(me, "DELETE", f"{path}/{done_column}")
    unknown = await task_bench.call(me, "PATCH", f"{path}/{uuid.uuid4()}", {"title": "Нет"})

    assert created.status_code == 201
    assert created.json() | {"id": None} == {
        "id": None, "title": "QA", "kind": "in_progress", "color": "teal", "collapsed": False,
    }  # fmt: skip
    assert columns[1] == created.json()["id"]
    assert (collapsed.json()["collapsed"], collapsed.json()["color"]) == (True, None)
    assert removed.status_code == 204
    assert cards_of(after, 1) == [*map(str, ideas), str(planned)]
    assert (last.status_code, code_of(last)) == (409, "last_column_of_kind")
    assert (unknown.status_code, code_of(unknown)) == (404, "column_not_found")


async def test_a_card_is_put_copied_and_moved_with_its_status(task_bench: TaskBench) -> None:
    me = uuid.uuid4()
    board_id = await made(task_bench, me)
    todo, doing, done = column_ids(await board(task_bench, me, board_id))
    path = f"/v1/boards/{board_id}/cards"

    first = await task_bench.call(
        me, "POST", path, {"title": "Первая", "column_id": todo, "position": 0}
    )
    on_top = await task_bench.call(
        me, "POST", path, {"title": "Верхняя", "column_id": todo, "position": 0}
    )
    await task_bench.call(
        me, "POST", f"/v1/tasks/{first.json()['id']}/subtasks", {"title": "Пункт"}
    )
    copy = await task_bench.call(
        me, "POST", path,
        {"title": "Копия", "column_id": done, "position": 0, "copy_of": first.json()["id"]},
    )  # fmt: skip
    moved = await task_bench.call(
        me, "PATCH", f"{path}/{first.json()['id']}", {"column_id": doing, "position": 0}
    )
    half = await task_bench.call(me, "PATCH", f"{path}/{first.json()['id']}", {"column_id": doing})
    renamed = await task_bench.call(
        me, "PATCH", f"{path}/{first.json()['id']}", {"title": "Новая", "priority": "high"}
    )
    elsewhere = await task_bench.call(me, "PATCH", f"{path}/{uuid.uuid4()}", {"title": "Чужая"})
    detail = await board(task_bench, me, board_id)

    assert (first.status_code, first.json()["status"]) == (201, "todo")
    assert cards_of(detail, 0) == [on_top.json()["id"]]
    assert (copy.json()["status"], copy.json()["subtasks_total"], copy.json()["subtasks_done"]) == (
        "done", 1, 0,
    )  # fmt: skip
    assert moved.json()["status"] == "in_progress"
    assert (half.status_code, code_of(half)) == (422, "validation_error")
    assert (renamed.json()["title"], renamed.json()["priority"]) == ("Новая", "high")
    assert (elsewhere.status_code, code_of(elsewhere)) == (404, "task_not_found")
    assert cards_of(detail, 1) == [first.json()["id"]]
    assert cards_of(detail, 2) == [copy.json()["id"]]


async def test_a_recurring_card_moved_to_done_comes_back_on_its_schedule_once(
    task_bench: TaskBench,
) -> None:
    me = uuid.uuid4()
    board_id = await made(task_bench, me)
    todo, _, done = column_ids(await board(task_bench, me, board_id))
    due = datetime.now(UTC).date() - timedelta(days=2)
    task = await task_bench.task(
        me,
        title="Weekly release notes",
        due_on=due,
        recurrence=recurrence_json(Recurrence(Every.DAY)),
    )
    await task_bench.place_in(me, task, (uuid.UUID(board_id), uuid.UUID(todo)))

    path = f"/v1/boards/{board_id}/cards/{task}"
    finished = await task_bench.call(me, "PATCH", path, {"column_id": done, "position": 0})
    await task_bench.call(me, "PATCH", path, {"column_id": todo, "position": 0})
    await task_bench.call(me, "PATCH", path, {"column_id": done, "position": 0})
    detail = await board(task_bench, me, board_id)

    cards = [card for column in detail["columns"] for card in column["cards"]]
    titles = [card["title"] for card in cards]
    assert finished.json()["status"] == "done"
    assert titles.count("Weekly release notes") == 2
    (next_card,) = [card for card in cards if card["id"] != str(task)]
    assert (next_card["recurring"], next_card["status"]) == (True, "todo")


async def test_a_workspace_task_is_not_copied(task_bench: TaskBench) -> None:
    me, org = uuid.uuid4(), uuid.uuid4()
    await task_bench.workspace(org, me)
    board_id = await made(task_bench, me)
    todo = column_ids(await board(task_bench, me, board_id))[0]
    shared = await task_bench.task(me, org)
    await task_bench.place_in(me, shared, (uuid.UUID(board_id), uuid.UUID(todo)))

    copy = await task_bench.call(
        me, "POST", f"/v1/boards/{board_id}/cards",
        {"title": "Копия", "column_id": todo, "position": 0, "copy_of": str(shared)},
    )  # fmt: skip

    assert (copy.status_code, code_of(copy)) == (409, "workspace_task_copy")


async def test_two_tabs_moving_cards_at_once_end_in_one_order_with_no_card_lost(
    task_bench: TaskBench,
) -> None:
    me = uuid.uuid4()
    board_id = await made(task_bench, me)
    todo, doing, _ = column_ids(await board(task_bench, me, board_id))
    tasks = [await task_bench.task(me) for _ in range(12)]
    for task in tasks:
        await task_bench.place_in(me, task, (uuid.UUID(board_id), uuid.UUID(todo)))

    async def move(task: uuid.UUID, column: str, position: int) -> int:
        body = {"column_id": column, "position": position}
        answer = await task_bench.call(me, "PATCH", f"/v1/boards/{board_id}/cards/{task}", body)
        return answer.status_code

    statuses = await asyncio.gather(
        *(move(task, doing if i % 2 else todo, i % 3) for i, task in enumerate(tasks))
    )
    detail = await board(task_bench, me, board_id)

    placed = cards_of(detail, 0) + cards_of(detail, 1)
    assert set(statuses) == {200}
    assert sorted(placed) == sorted(map(str, tasks))
    assert len(placed) == len(set(placed))
    assert len(cards_of(detail, 1)) == 6
