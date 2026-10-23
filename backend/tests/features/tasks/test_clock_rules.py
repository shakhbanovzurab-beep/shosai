"""The stopwatch under any sequence and under concurrent calls (tasks plan §3.9).

Hypothesis drives one task on a project board through starts, stops, resets, moves and
status changes from the panel, minutes apart, and holds the API's stopwatch to the mocks'
model; the database keeps one running span whatever arrives at once.
"""

import asyncio
import uuid
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import select

from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.tasks.domain.board_fields import StopwatchAutomations
from shosai.features.tasks.domain.clocks import Span, Stopwatch, stopwatch_of
from shosai.features.tasks.infrastructure.clock_records import TaskClockSpanRecord
from tests.features.tasks.board_helpers import board, made
from tests.features.tasks.clock_model import ClockModel
from tests.features.tasks.task_bench import HOME, TaskBench

T0 = datetime(2026, 10, 22, 9, tzinfo=UTC)
# Фикстура стенда чистит базу после теста; каждый пример берёт своего человека и доску.
CLOCK_PROPERTY = settings(
    max_examples=20, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
STEP = st.one_of(
    st.tuples(st.sampled_from(["start", "stop", "reset"]), st.just(0)),
    st.tuples(st.just("move"), st.integers(0, 4)),
    st.tuples(st.just("status"), st.integers(0, 2)),
)
STATUSES = ("todo", "in_progress", "done")


def shape(watch: Stopwatch | None) -> dict[str, object] | None:
    """The model's stopwatch as the API writes it."""
    if watch is None:
        return None
    since = watch.running_since
    return {
        "running_since": None if since is None else since.isoformat().replace("+00:00", "Z"),
        "total_ms": watch.total_ms,
        "by_column": {str(column): ms for column, ms in watch.by_column.items()},
    }


async def spans_of(bench: TaskBench, owner: uuid.UUID, task: uuid.UUID) -> list[Span]:
    """The task's spans as the database keeps them, oldest first."""
    spans = TaskClockSpanRecord
    scope = TenancyScope(HOME, owner)
    async with bench.homes.transactions.begin(scope, read_only=True) as session:
        rows = await session.execute(
            select(spans.column_id, spans.started_at, spans.stopped_at)
            .where(spans.task_id == task)
            .order_by(spans.started_at, spans.id)
        )
        return [Span(column, started, stopped) for column, started, stopped in rows]


async def running_spans(bench: TaskBench, owner: uuid.UUID, task: uuid.UUID) -> int:
    """How many spans of the task run."""
    return sum(span.stopped_at is None for span in await spans_of(bench, owner, task))


async def project(
    bench: TaskBench, who: uuid.UUID, automations: StopwatchAutomations, *, shown: bool
) -> tuple[str, list[dict[str, Any]], uuid.UUID]:
    """A project board with its stopwatch's settings, and a task in its first column."""
    board_id = await made(bench, who, "project")
    columns = (await board(bench, who, board_id))["columns"]
    settings_body = {"visible": shown, "automations": asdict(automations)}
    await bench.call(who, "PATCH", f"/v1/boards/{board_id}/stickers/stopwatch", settings_body)
    task = await bench.task(who)
    await bench.place_in(who, task, (uuid.UUID(board_id), uuid.UUID(columns[0]["id"])))
    return board_id, columns, task


@CLOCK_PROPERTY
@given(
    steps=st.lists(st.tuples(STEP, st.integers(0, 90)), max_size=10),
    automations=st.builds(StopwatchAutomations, st.booleans(), st.booleans(), st.booleans()),
    shown=st.booleans(),
)
async def test_any_sequence_answers_as_the_mocks(
    task_bench: TaskBench,
    steps: list[tuple[tuple[str, int], int]],
    automations: StopwatchAutomations,
    *,
    shown: bool,
) -> None:
    me, now = uuid.uuid4(), T0
    task_bench.clock.at(now)
    board_id, columns, task = await project(task_bench, me, automations, shown=shown)
    kinds = {uuid.UUID(column["id"]): str(column["kind"]) for column in columns}
    model = ClockModel(kinds, uuid.UUID(columns[0]["id"]), "todo", automations if shown else None)

    for (action, argument), pause in steps:
        now += timedelta(minutes=pause)
        task_bench.clock.at(now)
        if action in {"start", "stop", "reset"}:
            await task_bench.call(me, "POST", f"/v1/tasks/{task}/stopwatch/{action}")
            if action == "start":
                model.start(now)
            elif action == "stop":
                model.stop(now)
            else:
                model.reset()
        elif action == "move":
            target = columns[argument]["id"]
            await task_bench.call(
                me,
                "PATCH",
                f"/v1/boards/{board_id}/cards/{task}",
                {"column_id": target, "position": 0},
            )
            model.move(uuid.UUID(target), now)
        else:
            status = STATUSES[argument]
            await task_bench.call(me, "PATCH", f"/v1/tasks/{task}", {"status": status})
            model.set_status(status, now)

    answer = (await task_bench.call(me, "GET", f"/v1/tasks/{task}")).json()["stopwatch"]
    spans = await spans_of(task_bench, me, task)
    assert answer == shape(model.stopwatch())
    # Сводка в строке задачи — ровно сумма её отрезков.
    assert answer == shape(stopwatch_of(spans))
    if answer is not None:
        assert answer["total_ms"] == sum(answer["by_column"].values())
    assert sum(span.stopped_at is None for span in spans) <= 1


async def test_concurrent_starts_leave_one_running_span(task_bench: TaskBench) -> None:
    me = uuid.uuid4()
    task = await task_bench.task(me)

    answers = await asyncio.gather(
        *(task_bench.call(me, "POST", f"/v1/tasks/{task}/stopwatch/start") for _ in range(8))
    )

    assert {answer.status_code for answer in answers} == {200}
    assert await running_spans(task_bench, me, task) == 1


async def test_a_stop_racing_a_move_lands_in_one_order(task_bench: TaskBench) -> None:
    me = uuid.uuid4()
    task_bench.clock.at(T0)
    keeps = StopwatchAutomations(restart_on_move=False)
    board_id, columns, task = await project(task_bench, me, keeps, shown=True)
    await task_bench.call(me, "POST", f"/v1/tasks/{task}/stopwatch/start")
    task_bench.clock.at(T0 + timedelta(minutes=5))
    first, third = columns[0]["id"], columns[2]["id"]

    await asyncio.gather(
        task_bench.call(me, "POST", f"/v1/tasks/{task}/stopwatch/stop"),
        task_bench.call(
            me, "PATCH", f"/v1/boards/{board_id}/cards/{task}", {"column_id": third, "position": 0}
        ),
    )
    watch = (await task_bench.call(me, "GET", f"/v1/tasks/{task}")).json()["stopwatch"]

    # Стоп первым: перенос не запускает остановленный; перенос первым: стоп закрывает новый отрезок.
    stop_first = {"running_since": None, "total_ms": 300_000, "by_column": {first: 300_000}}
    move_first = {**stop_first, "by_column": {first: 300_000, third: 0}}
    assert watch in (stop_first, move_first)
    assert await running_spans(task_bench, me, task) == 0


async def test_a_panel_change_racing_a_card_move_waits_its_turn(task_bench: TaskBench) -> None:
    me = uuid.uuid4()
    board_id, columns, task = await project(task_bench, me, StopwatchAutomations(), shown=True)

    answers: list[httpx.Response] = []
    for step in range(6):
        card = {"column_id": columns[step % 5]["id"], "position": 0}
        answers += await asyncio.gather(
            task_bench.call(me, "PATCH", f"/v1/tasks/{task}", {"title": f"Шаг {step}"}),
            task_bench.call(me, "PATCH", f"/v1/boards/{board_id}/cards/{task}", card),
        )

    assert {answer.status_code for answer in answers} == {200}
