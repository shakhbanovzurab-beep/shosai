"""A task's checklist and comments answer as the cabinet's mocks do (tasks plan §3.12)."""

import uuid
from datetime import UTC, datetime, timedelta

import httpx

from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.tasks.domain.ranks import spaced_ranks
from shosai.features.tasks.domain.recurrence import Every, Recurrence, recurrence_json
from shosai.features.tasks.infrastructure.thread_records import TaskSubtaskRecord
from tests.features.tasks.task_bench import TaskBench


def code_of(answer: httpx.Response) -> str:
    """The refusal's code in the platform's envelope."""
    return str(answer.json()["error"]["code"])


async def comments_of(
    bench: TaskBench, who: uuid.UUID, task: uuid.UUID, query: str
) -> httpx.Response:
    """A page of the task's comments."""
    return await bench.call(who, "GET", f"/v1/tasks/{task}/comments{query}")


async def test_comments_page_by_key_so_a_comment_written_meanwhile_repeats_nothing(
    task_bench: TaskBench,
) -> None:
    me = uuid.uuid4()
    task = await task_bench.task(me)
    for number in range(12):
        await task_bench.call(me, "POST", f"/v1/tasks/{task}/comments", {"body": f"№{number}"})

    first = (await comments_of(task_bench, me, task, "?limit=5")).json()
    await task_bench.call(me, "POST", f"/v1/tasks/{task}/comments", {"body": "Пока читали"})
    second = (
        await comments_of(task_bench, me, task, f"?limit=5&cursor={first['next_cursor']}")
    ).json()
    third = (
        await comments_of(task_bench, me, task, f"?limit=5&cursor={second['next_cursor']}")
    ).json()

    seen = [item["body"] for page in (first, second, third) for item in page["items"]]
    assert seen == [f"№{number}" for number in reversed(range(12))]
    assert third["next_cursor"] is None


async def test_a_repeated_comment_is_one_comment_and_only_its_author_edits_it(
    task_bench: TaskBench,
) -> None:
    me, colleague, org = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    await task_bench.workspace(org, me, colleague)
    task_bench.profiles.names_by_person[me] = "Мария"
    task = await task_bench.task(me, org)
    theirs = await task_bench.call(
        colleague, "POST", f"/v1/tasks/{task}/comments", {"body": "Чужой"}
    )

    async def post() -> httpx.Response:
        key = {"Idempotency-Key": "k-1"}
        return await task_bench.call(
            me, "POST", f"/v1/tasks/{task}/comments", {"body": "Индексы"}, **key
        )

    first, again = await post(), await post()
    page = (await comments_of(task_bench, me, task, "?limit=2")).json()
    foreign = await task_bench.call(
        me, "PATCH", f"/v1/tasks/{task}/comments/{theirs.json()['id']}", {"body": "Моё"}
    )
    removed = await task_bench.call(
        me, "DELETE", f"/v1/tasks/{task}/comments/{theirs.json()['id']}"
    )
    edited = await task_bench.call(
        me, "PATCH", f"/v1/tasks/{task}/comments/{first.json()['id']}", {"body": "  Индексы потом "}
    )

    assert (first.status_code, again.json()["id"]) == (201, first.json()["id"])
    assert page["items"][0]["author"] == {"user_id": str(me), "name": "Мария", "is_you": True}
    assert [item["id"] for item in page["items"]] == [first.json()["id"], theirs.json()["id"]]
    assert page["items"][1]["author"]["is_you"] is False
    assert [(a.status_code, code_of(a)) for a in (foreign, removed)] == [
        (403, "not_comment_author"), (403, "not_comment_author"),
    ]  # fmt: skip
    assert (edited.json()["body"], edited.json()["edited_at"] is not None) == (
        "Индексы потом",
        True,
    )


async def test_comments_and_lines_are_refused_with_the_cabinets_codes(
    task_bench: TaskBench,
) -> None:
    me = uuid.uuid4()
    task = await task_bench.task(me)
    path = f"/v1/tasks/{task}"

    refusals = [
        await task_bench.call(me, "POST", f"{path}/comments", {"body": "   "}),
        await task_bench.call(me, "POST", f"{path}/comments", {"body": "я" * 5001}),
        await task_bench.call(me, "POST", f"{path}/subtasks", {"title": " "}),
        await task_bench.call(me, "POST", f"{path}/subtasks", {"title": "я" * 201}),
        await task_bench.call(me, "PATCH", f"{path}/subtasks/{uuid.uuid4()}", {"done": True}),
        await task_bench.call(me, "PATCH", f"{path}/comments/{uuid.uuid4()}", {"body": "a"}),
        await task_bench.call(me, "GET", f"/v1/tasks/{uuid.uuid4()}/comments"),
        await task_bench.call(me, "GET", f"{path}/comments?cursor=nonsense"),
        await task_bench.call(uuid.uuid4(), "POST", f"{path}/subtasks", {"title": "Чужое"}),
    ]

    assert [(a.status_code, code_of(a)) for a in refusals] == [
        (422, "validation_error"), (422, "comment_too_long"), (422, "title_required"),
        (422, "title_too_long"), (404, "subtask_not_found"), (404, "comment_not_found"),
        (404, "task_not_found"), (422, "invalid_cursor"), (404, "task_not_found"),
    ]  # fmt: skip


async def test_a_checklist_keeps_its_order_and_the_card_counts_it(task_bench: TaskBench) -> None:
    me = uuid.uuid4()
    task = await task_bench.task(me)
    path = f"/v1/tasks/{task}/subtasks"

    a = (await task_bench.call(me, "POST", path, {"title": "А"})).json()
    await task_bench.call(me, "POST", path, {"title": "Б", "position": 0})
    c = (await task_bench.call(me, "POST", path, {"title": "В", "position": 99})).json()
    moved = await task_bench.call(me, "PATCH", f"{path}/{c['id']}", {"position": 1, "done": True})
    nulled = await task_bench.call(me, "PATCH", f"{path}/{c['id']}", {"done": None})
    await task_bench.call(me, "POST", f"/v1/tasks/{task}/comments", {"body": "Готово"})
    detail = (await task_bench.call(me, "GET", f"/v1/tasks/{task}")).json()
    gone = await task_bench.call(me, "DELETE", f"{path}/{a['id']}")
    (item,) = (await task_bench.call(me, "GET", "/v1/tasks")).json()["items"]

    assert moved.json() == {"id": c["id"], "title": "В", "done": True}
    assert (nulled.status_code, code_of(nulled)) == (422, "validation_error")
    assert [line["title"] for line in detail["subtasks"]] == ["Б", "В", "А"]
    assert (detail["subtasks_done"], detail["subtasks_total"], detail["comment_count"]) == (1, 3, 1)
    assert gone.status_code == 204
    assert (item["subtasks_done"], item["subtasks_total"], item["comment_count"]) == (1, 2, 1)


async def test_a_checklist_holds_a_hundred_lines(task_bench: TaskBench) -> None:
    me = uuid.uuid4()
    task = await task_bench.task(me)
    async with task_bench.homes.transactions.begin(TenancyScope(Home.EU, me)) as session:
        for rank in spaced_ranks(100):
            session.add(
                TaskSubtaskRecord(
                    id=uuid.uuid4(), task_id=task, user_id=me, title="Пункт", rank=rank
                )
            )

    full = await task_bench.call(me, "POST", f"/v1/tasks/{task}/subtasks", {"title": "Ещё"})

    assert (full.status_code, code_of(full)) == (409, "subtasks_full")


async def test_lines_and_new_or_deleted_comments_raise_the_boards_revision(
    task_bench: TaskBench,
) -> None:
    me = uuid.uuid4()
    task = await task_bench.task(me)
    board = await task_bench.board(me)
    await task_bench.place(me, task, board)

    line = await task_bench.call(me, "POST", f"/v1/tasks/{task}/subtasks", {"title": "Пункт"})
    comment = await task_bench.call(me, "POST", f"/v1/tasks/{task}/comments", {"body": "Да"})
    path = f"/v1/tasks/{task}/comments/{comment.json()['id']}"
    await task_bench.call(me, "PATCH", path, {"body": "Нет"})
    await task_bench.call(me, "DELETE", path)
    await task_bench.call(me, "DELETE", f"/v1/tasks/{task}/subtasks/{line.json()['id']}")

    assert await task_bench.revision(me, board[0]) == 5


async def test_the_next_recurring_task_takes_the_checklist_unticked(task_bench: TaskBench) -> None:
    me = uuid.uuid4()
    due = datetime.now(UTC).date() - timedelta(days=1)
    task = await task_bench.task(me, due_on=due, recurrence=recurrence_json(Recurrence(Every.DAY)))
    path = f"/v1/tasks/{task}/subtasks"
    first = (await task_bench.call(me, "POST", path, {"title": "Первый"})).json()
    await task_bench.call(me, "POST", path, {"title": "Второй"})
    await task_bench.call(me, "PATCH", f"{path}/{first['id']}", {"done": True})
    await task_bench.call(me, "POST", f"/v1/tasks/{task}/comments", {"body": "Не переносится"})

    await task_bench.call(me, "PATCH", f"/v1/tasks/{task}", {"status": "done"})
    (next_task,) = (await task_bench.call(me, "GET", "/v1/tasks?status=open")).json()["items"]
    detail = (await task_bench.call(me, "GET", f"/v1/tasks/{next_task['id']}")).json()

    assert [(line["title"], line["done"]) for line in detail["subtasks"]] == [
        ("Первый", False), ("Второй", False),
    ]  # fmt: skip
    assert detail["comment_count"] == 0
