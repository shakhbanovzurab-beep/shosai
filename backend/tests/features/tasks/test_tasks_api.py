"""The one task API answers as the cabinet's mocks do (tasks plan §3.11, `tasks-routes.test.ts`)."""

import uuid
from datetime import UTC, date, datetime, timedelta

import httpx

from shosai.features.tasks.domain.recurrence import Every, Recurrence, next_due, recurrence_json
from tests.features.tasks.task_bench import TaskBench

# Поля задачи ровно как у `TaskDetail` кабинета (`domain/tasks-contract.ts`, `time-contract.ts`).
DETAIL_FIELDS = {
    "id", "title", "status", "priority", "starts_on", "due_on", "assignee", "cover", "values",
    "subtasks_done", "subtasks_total", "comment_count", "attachment_count", "recurring",
    "leo_fields", "space", "jira", "source_chat", "can_delete", "stopwatch", "timer",
    "time_tracking", "description", "recurrence", "other_values", "source", "subtasks",
    "attachments", "placement", "created_at", "updated_at", "completed_at", "server_now",
}  # fmt: skip


def code_of(answer: httpx.Response) -> str:
    """The refusal's code in the platform's envelope."""
    return str(answer.json()["error"]["code"])


async def test_a_task_made_by_hand_reads_back_with_every_field_of_the_panel(
    task_bench: TaskBench,
) -> None:
    me = uuid.uuid4()

    made = await task_bench.call(me, "POST", "/v1/tasks", {"title": "  Отправить договор "})
    read = await task_bench.call(me, "GET", f"/v1/tasks/{made.json()['id']}")

    assert made.status_code == 201
    assert set(made.json()) == DETAIL_FIELDS
    assert read.json() | {"server_now": None} == made.json() | {"server_now": None}
    body = read.json()
    assert (body["title"], body["status"], body["priority"], body["can_delete"]) == (
        "Отправить договор", "todo", None, True,
    )  # fmt: skip
    assert body["source"] == {"kind": "manual", "meeting": None, "finding": None, "chat": None}
    assert (body["values"], body["subtasks"], body["stopwatch"], body["placement"]) == (
        {}, [], None, None,
    )  # fmt: skip


async def test_a_repeated_key_answers_the_same_task_and_a_key_reused_otherwise_is_refused(
    task_bench: TaskBench,
) -> None:
    me = uuid.uuid4()
    key = {"Idempotency-Key": "make-1"}

    first = await task_bench.call(me, "POST", "/v1/tasks", {"title": "Один"}, **key)
    again = await task_bench.call(me, "POST", "/v1/tasks", {"title": "Один"}, **key)
    other = await task_bench.call(me, "POST", "/v1/tasks", {"title": "Другой"}, **key)

    assert again.json()["id"] == first.json()["id"]
    assert (other.status_code, code_of(other)) == (422, "idempotency_key_reused")


async def test_titles_and_bodies_are_refused_with_the_cabinets_codes(task_bench: TaskBench) -> None:
    me = uuid.uuid4()
    task = await task_bench.task(me)

    empty = await task_bench.call(me, "POST", "/v1/tasks", {"title": "   "})
    long = await task_bench.call(me, "PATCH", f"/v1/tasks/{task}", {"title": "я" * 201})
    nulled = await task_bench.call(me, "PATCH", f"/v1/tasks/{task}", {"title": None})
    unknown = await task_bench.call(me, "PATCH", f"/v1/tasks/{task}", {"colour": "red"})
    member = await task_bench.call(me, "PATCH", f"/v1/tasks/{task}", {"assignee_id": str(me)})

    assert [(a.status_code, code_of(a)) for a in (empty, long, nulled, unknown, member)] == [
        (422, "title_required"), (422, "title_too_long"), (422, "validation_error"),
        (422, "validation_error"), (422, "validation_error"),
    ]  # fmt: skip


async def test_a_person_s_change_drops_leo_s_mark_from_that_field_only(
    task_bench: TaskBench,
) -> None:
    me = uuid.uuid4()
    task = await task_bench.task(me, leo_fields=["assignee", "due", "priority"])

    answer = await task_bench.call(me, "PATCH", f"/v1/tasks/{task}", {"due_on": "2026-12-01"})

    assert answer.json()["leo_fields"] == ["assignee", "priority"]


async def test_null_clears_a_field_and_a_range_stays_inside_its_due_day(
    task_bench: TaskBench,
) -> None:
    me = uuid.uuid4()
    task = await task_bench.task(me, priority="high", due_on=date(2099, 1, 5))

    cleared = await task_bench.call(me, "PATCH", f"/v1/tasks/{task}", {"priority": None})
    ranged = await task_bench.call(
        me, "PATCH", f"/v1/tasks/{task}", {"starts_on": "2099-01-02", "due_on": "2099-01-01"}
    )
    no_due = await task_bench.call(
        me, "PATCH", f"/v1/tasks/{task}", {"starts_on": "2099-01-01", "due_on": None}
    )

    assert cleared.json()["priority"] is None
    assert (ranged.status_code, code_of(ranged)) == (422, "range_invalid")
    assert (no_due.json()["starts_on"], no_due.json()["due_on"]) == (None, None)


async def test_a_schedule_gives_a_task_its_first_date_and_a_week_needs_a_day(
    task_bench: TaskBench,
) -> None:
    me = uuid.uuid4()
    task = await task_bench.task(me)

    daily = await task_bench.call(
        me, "PATCH", f"/v1/tasks/{task}", {"recurrence": {"every": "day"}}
    )
    empty = await task_bench.call(
        me, "PATCH", f"/v1/tasks/{task}", {"recurrence": {"every": "week", "weekdays": []}}
    )
    twice = await task_bench.call(
        me,
        "PATCH",
        f"/v1/tasks/{task}",
        {"recurrence": {"every": "week", "weekdays": ["mon", "mon"]}},
    )

    assert daily.json()["due_on"] == datetime.now(UTC).date().isoformat()
    assert daily.json()["recurring"] is True
    assert empty.status_code == 422
    assert (twice.status_code, code_of(twice)) == (422, "recurrence_invalid")


async def test_a_batch_is_deleted_all_or_none(task_bench: TaskBench) -> None:
    me = uuid.uuid4()
    task = await task_bench.task(me)

    refused = await task_bench.call(
        me, "POST", "/v1/tasks/delete", {"task_ids": [str(task), str(uuid.uuid4())]}
    )
    still = await task_bench.call(me, "GET", f"/v1/tasks/{task}")
    deleted = await task_bench.call(me, "POST", "/v1/tasks/delete", {"task_ids": [str(task)]})
    gone = await task_bench.call(me, "GET", f"/v1/tasks/{task}")

    assert (refused.status_code, code_of(refused)) == (404, "task_not_found")
    assert still.status_code == 200
    assert (deleted.status_code, gone.status_code, code_of(gone)) == (204, 404, "task_not_found")


async def test_a_recurring_task_done_makes_its_next_one_once_at_the_top_of_its_board(
    task_bench: TaskBench,
) -> None:
    me = uuid.uuid4()
    due = datetime.now(UTC).date() - timedelta(days=3)
    rule = Recurrence(Every.DAY)
    task = await task_bench.task(me, due_on=due, recurrence=recurrence_json(rule))
    board = await task_bench.board(me)
    await task_bench.place(me, task, board)

    done = await task_bench.call(me, "PATCH", f"/v1/tasks/{task}", {"status": "done"})
    await task_bench.call(me, "PATCH", f"/v1/tasks/{task}", {"status": "todo"})
    await task_bench.call(me, "PATCH", f"/v1/tasks/{task}", {"status": "done"})
    page = await task_bench.call(me, "GET", "/v1/tasks?status=open")

    assert done.json()["recurring"] is False
    assert done.json()["completed_at"] is not None
    (next_task,) = page.json()["items"]
    assert next_task["due_on"] == next_due(rule, due, datetime.now(UTC).date()).isoformat()
    assert next_task["recurring"] is True
    detail = (await task_bench.call(me, "GET", f"/v1/tasks/{next_task['id']}")).json()
    assert detail["placement"] == {"board_id": str(board[0]), "column_id": str(board[1])}


async def test_each_change_publishes_exactly_its_events(task_bench: TaskBench) -> None:
    me = uuid.uuid4()

    made = await task_bench.call(
        me, "POST", "/v1/tasks", {"title": "С событиями", "due_on": "2099-01-01"}
    )
    task = made.json()["id"]
    await task_bench.call(me, "PATCH", f"/v1/tasks/{task}", {"title": "Без событий"})
    await task_bench.call(me, "PATCH", f"/v1/tasks/{task}", {"status": "done"})
    await task_bench.call(me, "PATCH", f"/v1/tasks/{task}", {"status": "in_progress"})
    await task_bench.call(me, "PATCH", f"/v1/tasks/{task}", {"due_on": None})
    await task_bench.call(me, "DELETE", f"/v1/tasks/{task}")

    assert await task_bench.events(uuid.UUID(task)) == [
        "tasks.task.due_changed", "tasks.task.completed", "tasks.task.reopened",
        "tasks.task.due_changed", "tasks.task.deleted",
    ]  # fmt: skip


async def test_a_change_raises_the_revision_of_the_readers_board(task_bench: TaskBench) -> None:
    me = uuid.uuid4()
    task = await task_bench.task(me)
    board = await task_bench.board(me)
    await task_bench.place(me, task, board)

    await task_bench.call(me, "PATCH", f"/v1/tasks/{task}", {"title": "Новое"})
    await task_bench.call(me, "PATCH", f"/v1/tasks/{task}", {"priority": "low"})

    assert await task_bench.revision(me, board[0]) == 3
