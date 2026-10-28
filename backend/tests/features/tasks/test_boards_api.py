"""Boards answer as the cabinet's mocks do (tasks plan §3.14, `boards-routes.test.ts`)."""

import uuid
from datetime import UTC, datetime, timedelta

from tests.features.tasks.board_helpers import board, cards_of, code_of, column_ids, made
from tests.features.tasks.task_bench import TaskBench


async def test_a_board_is_made_from_its_template_in_the_requests_language(
    task_bench: TaskBench,
) -> None:
    me = uuid.uuid4()

    russian = await board(task_bench, me, await made(task_bench, me, "project"))
    german = await board(
        task_bench,
        me,
        await made(task_bench, me, "simple", **{"Accept-Language": "de-DE,de;q=0.9"}),
    )

    assert [c["title"] for c in russian["columns"]] == [
        "Бэклог", "К выполнению", "В работе", "На проверке", "Готово",
    ]  # fmt: skip
    assert [c["kind"] for c in russian["columns"]] == [
        "todo", "todo", "in_progress", "in_progress", "done",
    ]  # fmt: skip
    assert [c["title"] for c in german["columns"]] == ["Zu erledigen", "In Arbeit", "Erledigt"]
    assert set(russian) == {"board", "stickers", "columns", "revision", "server_now"}
    assert russian["board"] | {"id": None, "created_at": None} == {
        "id": None, "name": "Работа", "icon": "briefcase", "jira": None, "incoming": True,
        "task_count": 0, "created_at": None,
    }  # fmt: skip
    assert [(s["id"], s["visible"]) for s in russian["stickers"]] == [
        ("assignee", True), ("due", True), ("priority", True), ("recurrence", False),
        ("stopwatch", False), ("timer", False), ("time_tracking", False),
    ]  # fmt: skip
    stopwatch = russian["stickers"][4]
    assert stopwatch["automations"] == {
        "start_on_arrival": False, "restart_on_move": True, "stop_on_done": True,
    }  # fmt: skip
    assert "automations" not in russian["stickers"][0]
    assert russian["columns"][0] | {"id": None, "cards": []} == {
        "id": None, "title": "Бэклог", "kind": "todo", "color": None, "collapsed": False,
        "cards": [],
    }  # fmt: skip


async def test_a_list_counts_what_boards_show_and_lands_waiting_work_on_the_first_board(
    task_bench: TaskBench,
) -> None:
    me, org = uuid.uuid4(), uuid.uuid4()
    await task_bench.workspace(org, me)
    board_id = await made(task_bench, me)
    columns = column_ids(await board(task_bench, me, board_id))
    long_ago = datetime.now(UTC) - timedelta(days=40)
    recent = datetime.now(UTC) - timedelta(days=5)
    shown = [
        await task_bench.task(me),
        await task_bench.task(me, status="done", completed_at=recent),
        await task_bench.task(me, status="done", completed_at=long_ago),
    ]
    for task in shown:
        await task_bench.place_in(me, task, (uuid.UUID(board_id), uuid.UUID(columns[0])))
    await task_bench.task(me, org, assignee_user_id=me)
    await task_bench.task(me, source="meeting", source_meeting_id=uuid.uuid4())
    # Задача, сделанная вручную, тоже не остаётся вне досок (правило владельца 2026-10-28).
    await task_bench.task(me, title="Своя")

    listed = (await task_bench.call(me, "GET", "/v1/boards")).json()
    stranger = await task_bench.call(uuid.uuid4(), "GET", f"/v1/boards/{board_id}")

    assert [item["task_count"] for item in listed["items"]] == [5]
    assert [item["incoming"] for item in listed["items"]] == [True]
    assert listed["incoming"] == {"board_id": board_id, "open": 0}
    assert (stranger.status_code, code_of(stranger)) == (404, "board_not_found")


async def test_incoming_tasks_land_once_on_top_of_the_first_column_of_their_kind(
    task_bench: TaskBench,
) -> None:
    me, org = uuid.uuid4(), uuid.uuid4()
    await task_bench.workspace(org, me)
    board_id = await made(task_bench, me, "project")
    assigned = await task_bench.task(me, org, assignee_user_id=me, status="in_progress")
    from_meeting = await task_bench.task(me, source="meeting", source_meeting_id=uuid.uuid4())

    chosen = await task_bench.call(me, "PUT", "/v1/boards/incoming", {"board_id": board_id})
    first = await board(task_bench, me, board_id)
    again = await board(task_bench, me, board_id)

    assert chosen.json()["incoming"] == {"board_id": board_id, "open": 0}
    assert [item["incoming"] for item in chosen.json()["items"]] == [True]
    assert cards_of(first, 0) == [str(from_meeting)]
    assert cards_of(first, 2) == [str(assigned)]
    assert first["columns"][2]["cards"][0]["space"]["workspace_id"] == str(org)
    assert cards_of(again, 0) == [str(from_meeting)]
    assert again["revision"] == first["revision"]


async def test_a_task_ticked_elsewhere_shows_in_a_done_column_at_the_next_read(
    task_bench: TaskBench,
) -> None:
    me = uuid.uuid4()
    board_id = await made(task_bench, me)
    columns = column_ids(await board(task_bench, me, board_id))
    staying, ticked = await task_bench.task(me), await task_bench.task(me)
    for task in (ticked, staying):
        await task_bench.place_in(me, task, (uuid.UUID(board_id), uuid.UUID(columns[0])))
    before = await board(task_bench, me, board_id)

    await task_bench.call(me, "PATCH", f"/v1/tasks/{ticked}", {"status": "done"})
    after = await board(task_bench, me, board_id)

    assert cards_of(after, 0) == [str(staying)]
    assert cards_of(after, 2) == [str(ticked)]
    assert after["revision"] > before["revision"]


async def test_a_board_is_renamed_laid_out_and_a_stale_layout_refused(
    task_bench: TaskBench,
) -> None:
    me = uuid.uuid4()
    board_id = await made(task_bench, me)
    detail = await board(task_bench, me, board_id)
    first, second = await task_bench.task(me), await task_bench.task(me)
    todo = uuid.UUID(column_ids(detail)[0])
    for task in (first, second):
        await task_bench.place_in(me, task, (uuid.UUID(board_id), todo))
    shown = cards_of(await board(task_bench, me, board_id), 0)
    layout = {
        "columns": [
            {
                "id": c["id"],
                "title": c["title"],
                "task_ids": list(reversed(shown)) if i == 0 else [],
            }
            for i, c in reversed(list(enumerate(detail["columns"])))
        ]
    }
    stale = {"columns": [{**c, "task_ids": []} for c in layout["columns"]]}

    renamed = await task_bench.call(
        me, "PATCH", f"/v1/boards/{board_id}", {"name": " Дом ", "icon": "home"}
    )
    nulled = await task_bench.call(me, "PATCH", f"/v1/boards/{board_id}", {"name": None})
    laid = await task_bench.call(me, "PUT", f"/v1/boards/{board_id}/layout", layout)
    refused = await task_bench.call(me, "PUT", f"/v1/boards/{board_id}/layout", stale)
    after = await board(task_bench, me, board_id)

    assert (renamed.json()["name"], renamed.json()["icon"]) == ("Дом", "home")
    assert (nulled.status_code, laid.status_code) == (422, 204)
    assert (refused.status_code, code_of(refused)) == (409, "board_changed")
    assert [c["kind"] for c in after["columns"]] == ["done", "in_progress", "todo"]
    assert cards_of(after, 2) == list(reversed(shown))


async def test_deleting_a_board_deletes_its_hand_made_tasks_and_keeps_the_rest(
    task_bench: TaskBench,
) -> None:
    me, org = uuid.uuid4(), uuid.uuid4()
    await task_bench.workspace(org, me)
    board_id = await made(task_bench, me)
    await task_bench.call(me, "PUT", "/v1/boards/incoming", {"board_id": board_id})
    todo = uuid.UUID(column_ids(await board(task_bench, me, board_id))[0])
    own = await task_bench.task(me)
    shared = await task_bench.task(me, org, assignee_user_id=me)
    meeting = await task_bench.task(me, source="meeting", source_meeting_id=uuid.uuid4())
    await task_bench.place_in(me, own, (uuid.UUID(board_id), todo))
    await board(task_bench, me, board_id)

    gone = await task_bench.call(me, "DELETE", f"/v1/boards/{board_id}")
    listed = (await task_bench.call(me, "GET", "/v1/boards")).json()
    reads = [
        await task_bench.call(me, "GET", f"/v1/tasks/{task}") for task in (own, shared, meeting)
    ]

    assert gone.status_code == 204
    assert listed == {"items": [], "incoming": {"board_id": None, "open": 2}}
    assert [answer.status_code for answer in reads] == [404, 200, 200]
    assert await task_bench.events(own) == ["tasks.task.deleted"]


async def test_jira_answers_as_without_a_connection(task_bench: TaskBench) -> None:
    me = uuid.uuid4()
    board_id = await made(task_bench, me)

    available = await task_bench.call(me, "GET", "/v1/boards/jira/available")
    connect = await task_bench.call(
        me, "POST", "/v1/boards/jira", {"site": "acme.atlassian.net", "board_id": 7}
    )
    sync = await task_bench.call(me, "POST", f"/v1/boards/{board_id}/sync")

    assert available.json() == {"connected": False, "account": None, "items": []}
    assert (connect.status_code, code_of(connect)) == (409, "connect_jira_first")
    assert (sync.status_code, code_of(sync)) == (409, "not_jira_board")
