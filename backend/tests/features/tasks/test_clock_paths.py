"""The automations on every path a task takes, and who sees its clocks (tasks plan §3.9).

A task landing on the incoming board starts where the board asks — a workspace's too,
through the database's function, which starts nothing that did not come to the person; a
status changed in the panel acts on the changer's board as its next read moves the card,
and on no one else's; a recurring task's next one keeps the plan, not the fact; the spans
open to exactly those who may read the task.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.tasks.domain.recurrence import Every, Recurrence, recurrence_json
from shosai.features.tasks.infrastructure.task_records import TASK_RESOURCE
from shosai.features.workspaces.contracts import Viewer
from tests.features.tasks.board_helpers import board, column_ids, made
from tests.features.tasks.task_bench import HOME, PARENTS, TaskBench, task_columns
from tests.harness.connections import Connection
from tests.harness.run_slot import RunSlot
from tests.support.access_model import ResourceRow
from tests.support.isolation import assert_isolated

T0 = datetime(2026, 10, 22, 9, tzinfo=UTC)
ARRIVAL = {"start_on_arrival": True, "restart_on_move": True, "stop_on_done": True}
SPAN = (
    "INSERT INTO task_clock_spans (id, task_id, user_id, org_id, column_id, started_at,"
    " stopped_at) VALUES (%s, %s, %s, %s, NULL, now() - interval '1 hour', now())"
)
SUMMED = (
    "UPDATE tasks SET stopwatch_total_ms = 3600000, stopwatch_by_column = '{}'::jsonb WHERE id = %s"
)


async def automated(bench: TaskBench, who: uuid.UUID, board_id: str, automations: object) -> None:
    """The board shows the stopwatch with these automations."""
    body = {"visible": True, "automations": automations}
    answer = await bench.call(who, "PATCH", f"/v1/boards/{board_id}/stickers/stopwatch", body)
    assert answer.status_code == 200, answer.text


async def test_landed_tasks_start_where_the_incoming_board_asks(task_bench: TaskBench) -> None:
    me, colleague, org = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    await task_bench.workspace(org, colleague, me)
    task_bench.clock.at(T0)
    board_id = await made(task_bench, me, "project")
    await automated(task_bench, me, board_id, ARRIVAL)
    assigned = await task_bench.task(colleague, org, assignee_user_id=me)
    from_meeting = await task_bench.task(me, source="meeting", source_meeting_id=uuid.uuid4())

    await task_bench.call(me, "PUT", "/v1/boards/incoming", {"board_id": board_id})
    cards = {card["id"]: card for c in (await board(task_bench, me, board_id))["columns"]
             for card in c["cards"]}  # fmt: skip

    since = T0.isoformat().replace("+00:00", "Z")
    assert cards[str(assigned)]["stopwatch"]["running_since"] == since
    assert cards[str(from_meeting)]["stopwatch"]["running_since"] == since


async def test_the_landing_function_starts_only_what_came_to_the_person(
    task_bench: TaskBench,
) -> None:
    me, colleague, org = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    await task_bench.workspace(org, colleague, me)
    board_id = await made(task_bench, me)
    column = uuid.UUID(column_ids(await board(task_bench, me, board_id))[0])
    theirs = await task_bench.task(colleague, org, assignee_user_id=colleague)
    mine = await task_bench.task(colleague, org, assignee_user_id=me)
    for task in (theirs, mine):
        await task_bench.place_in(me, task, (uuid.UUID(board_id), column))

    async with task_bench.homes.transactions.begin(TenancyScope(HOME, me)) as session:
        started = await session.scalar(
            text(
                "SELECT tasks_start_landed(CAST(:tasks AS uuid[]), CAST(:columns AS uuid[]), now())"
            ),
            {"tasks": [theirs, mine, mine], "columns": [column, column, uuid.uuid4()]},
        )

    assert started == 1
    watches = [
        (await task_bench.call(me, "GET", f"/v1/tasks/{task}")).json()["stopwatch"]
        for task in (theirs, mine)
    ]
    assert watches[0] is None
    assert watches[1]["running_since"] is not None


async def test_a_status_set_in_the_panel_acts_on_the_changers_board_only(
    task_bench: TaskBench,
) -> None:
    me, colleague, org = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    await task_bench.workspace(org, me, colleague)
    task_bench.clock.at(T0)
    mine, theirs = await made(task_bench, me), await made(task_bench, colleague)
    await automated(task_bench, me, mine, ARRIVAL)
    await automated(task_bench, colleague, theirs, {**ARRIVAL, "stop_on_done": False})
    task = await task_bench.task(me, org)
    for who, board_id in ((me, mine), (colleague, theirs)):
        first = uuid.UUID(column_ids(await board(task_bench, who, board_id))[0])
        await task_bench.place_in(who, task, (uuid.UUID(board_id), first))
    await task_bench.call(colleague, "POST", f"/v1/tasks/{task}/stopwatch/start")

    task_bench.clock.at(T0 + timedelta(minutes=20))
    await task_bench.call(me, "PATCH", f"/v1/tasks/{task}", {"status": "in_progress"})
    task_bench.clock.at(T0 + timedelta(minutes=50))
    await task_bench.call(me, "PATCH", f"/v1/tasks/{task}", {"status": "done"})
    await board(task_bench, colleague, theirs)
    watch = (await task_bench.call(me, "GET", f"/v1/tasks/{task}")).json()["stopwatch"]

    columns = column_ids(await board(task_bench, me, mine))
    theirs_first = column_ids(await board(task_bench, colleague, theirs))[0]
    assert watch == {
        "running_since": None, "total_ms": 50 * 60_000,
        "by_column": {theirs_first: 20 * 60_000, columns[1]: 30 * 60_000},
    }  # fmt: skip


async def test_a_recurring_tasks_next_one_keeps_the_plan_not_the_fact(
    task_bench: TaskBench,
) -> None:
    me = uuid.uuid4()
    task = await task_bench.task(
        me,
        due_on=datetime.now(UTC).date(),
        recurrence=recurrence_json(Recurrence(Every.DAY)),
        plan_minutes=30,
        fact_minutes=25,
    )

    await task_bench.call(me, "PATCH", f"/v1/tasks/{task}", {"status": "done"})
    listed = (await task_bench.call(me, "GET", "/v1/tasks?status=open")).json()["items"]

    (following,) = listed
    assert following["time_tracking"] == {"plan_minutes": 30, "fact_minutes": None}


async def span_each(connection: Connection, rows: list[ResourceRow]) -> None:
    """A closed hour of the stopwatch on every task of the world."""
    async with connection.transaction():
        for row in rows:
            await connection.execute(SPAN, (uuid.uuid4(), row.id, row.owner, row.org_id))
            await connection.execute(SUMMED, (row.id,))


@pytest.mark.isolation(resource="task")
async def test_a_tasks_clocks_open_to_exactly_those_who_may_read_it(
    task_bench: TaskBench, run_slot: RunSlot
) -> None:
    connection = run_slot.claimed.connections[Home.EU]
    rows: list[ResourceRow] = []
    spanned: list[bool] = []

    async def path(viewer: Viewer) -> set[uuid.UUID]:
        if not spanned:
            await span_each(connection, rows)
            spanned.append(True)
        opened = set()
        for row in rows:
            answer = await task_bench.call(viewer.user_id, "GET", f"/v1/tasks/{row.id}")
            if answer.status_code == 200 and answer.json()["stopwatch"] is not None:
                opened.add(row.id)
        return opened

    def columns(row: ResourceRow) -> dict[str, object]:
        rows.append(row)
        return task_columns(row)

    await assert_isolated(connection, TASK_RESOURCE, path, columns, PARENTS)
