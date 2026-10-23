"""The stopwatch, the timer, plan and fact answer as the mocks' `clock-routes` tests (§3.9).

The mocks' Work board is a project board here — backlog, to do, in progress, review, done
for their ideas, planned, building and shipped — showing the stopwatch with its defaults.
"""

import uuid
from datetime import UTC, datetime, timedelta

from tests.features.tasks.board_helpers import board, code_of, column_ids, made
from tests.features.tasks.task_bench import Json, TaskBench

MINUTE = 60_000
T0 = datetime(2026, 10, 22, 9, tzinfo=UTC)
AUTOMATIONS = {"start_on_arrival": True, "restart_on_move": False, "stop_on_done": True}


def at(minutes: int) -> str:
    """The moment T0 plus minutes as the API writes it."""
    return (T0 + timedelta(minutes=minutes)).isoformat().replace("+00:00", "Z")


async def work(bench: TaskBench, who: uuid.UUID) -> tuple[str, list[str], uuid.UUID]:
    """A project board showing the stopwatch, and a task in its first column."""
    board_id = await made(bench, who, "project")
    columns = column_ids(await board(bench, who, board_id))
    shown = await bench.call(
        who, "PATCH", f"/v1/boards/{board_id}/stickers/stopwatch", {"visible": True}
    )
    assert shown.status_code == 200, shown.text
    task = await bench.task(who)
    await bench.place_in(who, task, (uuid.UUID(board_id), uuid.UUID(columns[0])))
    return board_id, columns, task


async def clock(bench: TaskBench, who: uuid.UUID, task: uuid.UUID, action: str) -> Json:
    """A clock's action and its answer."""
    answer = await bench.call(who, "POST", f"/v1/tasks/{task}/{action}")
    assert answer.status_code == 200, answer.text
    found: Json = answer.json()
    return found


async def move(bench: TaskBench, who: uuid.UUID, board_id: str, task: uuid.UUID, to: str) -> Json:
    """The card moved to the top of a column."""
    answer = await bench.call(
        who, "PATCH", f"/v1/boards/{board_id}/cards/{task}", {"column_id": to, "position": 0}
    )
    assert answer.status_code == 200, answer.text
    found: Json = answer.json()
    return found


async def stopwatch_of(bench: TaskBench, who: uuid.UUID, task: uuid.UUID) -> Json | None:
    """The task's stopwatch as its panel reads it."""
    found: Json | None = (await bench.call(who, "GET", f"/v1/tasks/{task}")).json()["stopwatch"]
    return found


async def test_time_counts_per_column_and_a_repeat_changes_nothing(task_bench: TaskBench) -> None:
    me = uuid.uuid4()
    task_bench.clock.at(T0)
    board_id, (ideas, planned, *_), task = await work(task_bench, me)

    started = await clock(task_bench, me, task, "stopwatch/start")
    await clock(task_bench, me, task, "stopwatch/start")
    task_bench.clock.at(T0 + timedelta(minutes=30))
    await move(task_bench, me, board_id, task, planned)
    task_bench.clock.at(T0 + timedelta(minutes=80))
    stopped = await clock(task_bench, me, task, "stopwatch/stop")
    again = await clock(task_bench, me, task, "stopwatch/stop")
    reset = await clock(task_bench, me, task, "stopwatch/reset")

    assert (started["stopwatch"]["running_since"], started["server_now"]) == (at(0), at(0))
    expected = {
        "running_since": None, "total_ms": 80 * MINUTE,
        "by_column": {ideas: 30 * MINUTE, planned: 50 * MINUTE},
    }  # fmt: skip
    assert stopped["stopwatch"] == again["stopwatch"] == expected
    assert reset["stopwatch"] is None


async def test_a_move_restarts_it_and_done_stops_it(task_bench: TaskBench) -> None:
    me = uuid.uuid4()
    task_bench.clock.at(T0 + timedelta(minutes=10))
    board_id, (_, _, building, _, shipped), task = await work(task_bench, me)

    card = await move(task_bench, me, board_id, task, building)
    task_bench.clock.at(T0 + timedelta(minutes=40))
    await move(task_bench, me, board_id, task, shipped)

    assert card["stopwatch"]["running_since"] == at(10)
    assert await stopwatch_of(task_bench, me, task) == {
        "running_since": None, "total_ms": 30 * MINUTE, "by_column": {building: 30 * MINUTE},
    }  # fmt: skip


async def test_it_starts_on_arrival_only_where_the_board_asks(task_bench: TaskBench) -> None:
    me = uuid.uuid4()
    task_bench.clock.at(T0)
    board_id, (ideas, planned, *_), resting = await work(task_bench, me)
    path = f"/v1/boards/{board_id}/stickers/stopwatch"
    await task_bench.call(me, "PATCH", path, {"automations": AUTOMATIONS})
    quiet = await made(task_bench, me)
    quiet_column = column_ids(await board(task_bench, me, quiet))[0]

    fresh = await task_bench.call(
        me,
        "POST",
        f"/v1/boards/{board_id}/cards",
        {"title": "Fresh", "column_id": ideas, "position": 0},
    )
    await move(task_bench, me, board_id, resting, planned)
    there = await task_bench.call(
        me,
        "POST",
        f"/v1/boards/{quiet}/cards",
        {"title": "Quiet", "column_id": quiet_column, "position": 0},
    )

    assert fresh.json()["stopwatch"]["running_since"] == at(0)
    assert await stopwatch_of(task_bench, me, resting) is None
    assert there.json()["stopwatch"] is None


async def test_a_jira_task_has_no_clocks(task_bench: TaskBench) -> None:
    me = uuid.uuid4()
    task = await task_bench.task(me, source="jira")

    refusals = [
        await task_bench.call(me, "POST", f"/v1/tasks/{task}/stopwatch/start"),
        await task_bench.call(me, "POST", f"/v1/tasks/{task}/timer/pause"),
        await task_bench.call(me, "PATCH", f"/v1/tasks/{task}", {"plan_minutes": 30}),
    ]

    assert [(a.status_code, code_of(a)) for a in refusals] == [(409, "jira_unsupported")] * 3


async def test_the_timer_pauses_resumes_and_counts_past_zero(task_bench: TaskBench) -> None:
    me = uuid.uuid4()
    task = await task_bench.task(me)
    path = f"/v1/tasks/{task}/timer"
    task_bench.clock.at(T0)

    await task_bench.call(me, "PUT", path, {"length_ms": 60 * MINUTE})
    task_bench.clock.at(T0 + timedelta(minutes=10))
    paused = await clock(task_bench, me, task, "timer/pause")
    task_bench.clock.at(T0 + timedelta(minutes=40))
    resumed = await clock(task_bench, me, task, "timer/resume")
    again = await clock(task_bench, me, task, "timer/resume")
    task_bench.clock.at(T0 + timedelta(minutes=100))
    overrun = await clock(task_bench, me, task, "timer/pause")
    removed = await task_bench.call(me, "DELETE", path)

    assert paused["timer"] == {"length_ms": 60 * MINUTE, "ends_at": None,
                               "paused_left_ms": 50 * MINUTE}  # fmt: skip
    assert resumed["timer"]["ends_at"] == again["timer"]["ends_at"] == at(90)
    assert overrun["timer"]["paused_left_ms"] == -10 * MINUTE
    assert removed.json()["timer"] is None


async def test_a_length_out_of_range_and_a_missing_timer_are_refused(
    task_bench: TaskBench,
) -> None:
    me = uuid.uuid4()
    task = await task_bench.task(me)

    short = await task_bench.call(me, "PUT", f"/v1/tasks/{task}/timer", {"length_ms": 1_000})
    long = await task_bench.call(
        me, "PUT", f"/v1/tasks/{task}/timer", {"length_ms": 365 * 24 * 60 * MINUTE + 1}
    )
    pause = await task_bench.call(me, "POST", f"/v1/tasks/{task}/timer/pause")
    foreign = await task_bench.call(uuid.uuid4(), "POST", f"/v1/tasks/{task}/stopwatch/start")

    assert [(a.status_code, code_of(a)) for a in (short, long, pause, foreign)] == [
        (422, "validation_error"), (422, "validation_error"), (409, "timer_not_set"),
        (404, "task_not_found"),
    ]  # fmt: skip


async def test_plan_and_fact_are_minutes_cleared_by_null_never_negative(
    task_bench: TaskBench,
) -> None:
    me = uuid.uuid4()
    task = await task_bench.task(me)
    path = f"/v1/tasks/{task}"

    set_both = await task_bench.call(me, "PATCH", path, {"plan_minutes": 240, "fact_minutes": 90})
    cleared = await task_bench.call(me, "PATCH", path, {"plan_minutes": None, "fact_minutes": None})
    negative = await task_bench.call(me, "PATCH", path, {"fact_minutes": -5})
    too_many = await task_bench.call(me, "PATCH", path, {"plan_minutes": 6_000_001})

    assert set_both.json()["time_tracking"] == {"plan_minutes": 240, "fact_minutes": 90}
    assert cleared.json()["time_tracking"] is None
    assert [(a.status_code, code_of(a)) for a in (negative, too_many)] == [
        (422, "validation_error")
    ] * 2
