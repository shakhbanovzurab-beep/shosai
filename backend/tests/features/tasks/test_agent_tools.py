"""Leo's read tools over tasks (step 7): only what the person may read, within budget."""

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest

from shosai.core.agent_tools.context import ToolContext
from shosai.core.agent_tools.provenance import Provenance
from shosai.core.agent_tools.results import ToolErrorCode
from shosai.core.ai.spend.estimates import tokens_of
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.tasks.application.leo_reads import LeoReads
from shosai.features.tasks.channels.agent_tool_models import ListBoard, SearchTasks
from shosai.features.tasks.channels.agent_tool_reads import TaskToolReads
from shosai.features.tasks.channels.agent_tools import (
    BOARD_BUDGET,
    READ_TOOLS,
    SEARCH_BUDGET,
)
from shosai.features.tasks.infrastructure.task_records import TASK_RESOURCE
from shosai.features.workspaces.contracts import Viewer
from tests.features.tasks.board_helpers import board, column_ids, made
from tests.features.tasks.task_bench import HOME, PARENTS, TaskBench
from tests.harness.run_slot import RunSlot
from tests.support.access_model import ResourceRow
from tests.support.isolation import assert_isolated

# Московский день: в 22:30 UTC там уже завтра.
NOW = datetime(2026, 10, 21, 22, 30, tzinfo=UTC)
TODAY = date(2026, 10, 22)


def context(who: uuid.UUID) -> ToolContext:
    """A call of the person's run."""
    return ToolContext(
        TenancyScope(HOME, who), uuid.uuid4(), datetime.now(UTC) + timedelta(seconds=30)
    )


def tools(bench: TaskBench) -> TaskToolReads:
    """The toolset's handlers over the bench, at the test's moment."""
    return TaskToolReads(LeoReads(bench.homes.transactions, bench.ports, lambda: NOW), lambda: NOW)


async def titles(bench: TaskBench, who: uuid.UUID, **filters: object) -> list[str]:
    """The titles a search finds."""
    found = await tools(bench).search(SearchTasks.model_validate(filters), context(who))
    assert found.output is not None
    return [task.title for task in found.output.tasks]


def test_both_tools_label_their_results_as_text_the_user_may_not_have_written() -> None:
    assert {spec.name: spec.provenance for spec in READ_TOOLS} == {
        "tasks.search": Provenance.TASK_FOREIGN, "tasks.list_board": Provenance.TASK_FOREIGN,
    }  # fmt: skip


async def test_the_search_finds_by_words_status_due_window_and_space(task_bench: TaskBench) -> None:
    me, org = uuid.uuid4(), uuid.uuid4()
    task_bench.profiles.zones[me] = "Europe/Moscow"
    await task_bench.workspace(org, me)
    await task_bench.task(me, title="Отчёт за квартал", due_on=TODAY - timedelta(days=1))
    await task_bench.task(me, title="Позвонить", due_on=TODAY)
    await task_bench.task(me, title="Неделя", due_on=TODAY + timedelta(days=2))
    await task_bench.task(me, title="Потом", due_on=TODAY + timedelta(days=4))
    await task_bench.task(
        me, title="Готово", status="done", completed_at=NOW, due_on=TODAY - timedelta(days=2)
    )
    await task_bench.task(me, org, title="Общий ОТЧЁТ", assignee_user_id=me)
    await task_bench.task(me, org, title="Чужая работа")

    assert await titles(task_bench, me, query="отчёт") == ["Отчёт за квартал", "Общий ОТЧЁТ"]
    assert await titles(task_bench, me, due="overdue") == ["Отчёт за квартал"]
    assert await titles(task_bench, me, due="today") == ["Позвонить"]
    assert await titles(task_bench, me, due="this_week", status="open") == [
        "Отчёт за квартал", "Позвонить", "Неделя",
    ]  # fmt: skip
    assert await titles(task_bench, me, status="done") == ["Готово"]
    assert await titles(task_bench, me, workspace_id=str(org)) == ["Общий ОТЧЁТ", "Чужая работа"]
    assert "Общий ОТЧЁТ" not in await titles(task_bench, me, personal=True)
    assert "Чужая работа" not in await titles(task_bench, me, mine=True)


async def test_a_found_task_says_where_its_card_sits_and_its_time(task_bench: TaskBench) -> None:
    me = uuid.uuid4()
    board_id = await made(task_bench, me)
    todo = uuid.UUID(column_ids(await board(task_bench, me, board_id))[0])
    task = await task_bench.task(
        me, title="Сверка", plan_minutes=60, fact_minutes=15,
        stopwatch_since=NOW - timedelta(minutes=5), stopwatch_total_ms=600_000,
        stopwatch_by_column={},
    )  # fmt: skip
    await task_bench.place_in(me, task, (uuid.UUID(board_id), todo))

    found = await tools(task_bench).search(SearchTasks(board_id=uuid.UUID(board_id)), context(me))

    assert found.output is not None
    (one,) = found.output.tasks
    assert one.on_board is not None
    assert one.on_board.board_id == uuid.UUID(board_id)
    assert one.time.model_dump() == {
        "plan_minutes": 60, "fact_minutes": 15, "stopwatch_ms": 900_000, "stopwatch_running": True,
    }  # fmt: skip


async def test_a_board_reads_its_columns_and_names_the_other_boards(task_bench: TaskBench) -> None:
    me = uuid.uuid4()
    first, second = await made(task_bench, me), await made(task_bench, me)
    todo = uuid.UUID(column_ids(await board(task_bench, me, first))[0])
    for n in range(25):
        task = await task_bench.task(me, title=f"Карточка {n}")
        await task_bench.place_in(me, task, (uuid.UUID(first), todo))

    read = await tools(task_bench).list_board(ListBoard(), context(me))
    foreign = await tools(task_bench).list_board(
        ListBoard(board_id=uuid.UUID(second)), context(uuid.uuid4())
    )

    assert read.output is not None
    assert read.output.board.board_id == uuid.UUID(first)
    to_do = read.output.columns[0]
    assert (len(to_do.cards), to_do.more) == (20, 5)
    assert [b.board_id for b in read.output.other_boards] == [uuid.UUID(second)]
    assert foreign.error is not None
    assert foreign.error.code is ToolErrorCode.NOT_FOUND


async def test_the_results_stay_within_their_budgets(task_bench: TaskBench) -> None:
    me = uuid.uuid4()
    board_id = await made(task_bench, me)
    columns = column_ids(await board(task_bench, me, board_id))
    kinds = ("todo", "in_progress", "done")
    for n in range(90):
        kind = kinds[n % 3]
        task = await task_bench.task(
            me, title=f"{n:02} " + "долгое название " * 12, status=kind,
            completed_at=NOW if kind == "done" else None,
        )  # fmt: skip
        await task_bench.place_in(me, task, (uuid.UUID(board_id), uuid.UUID(columns[n % 3])))

    found = await tools(task_bench).search(SearchTasks(limit=20), context(me))
    read = await tools(task_bench).list_board(ListBoard(), context(me))

    assert found.output is not None
    assert read.output is not None
    assert len(found.output.tasks) == 20
    assert sum(len(column.cards) for column in read.output.columns) == 60
    assert tokens_of(found.output.model_dump_json()) <= SEARCH_BUDGET
    assert tokens_of(read.output.model_dump_json()) <= BOARD_BUDGET


@pytest.mark.isolation(resource="task")
async def test_a_tool_never_returns_a_task_the_person_may_not_read(
    task_bench: TaskBench, run_slot: RunSlot
) -> None:
    connection = run_slot.claimed.connections[Home.EU]
    rows: list[ResourceRow] = []

    async def path(viewer: Viewer) -> set[uuid.UUID]:
        opened = set()
        for row in rows:
            args = SearchTasks(query=str(row.id)[:13], limit=1)
            found = await tools(task_bench).search(args, context(viewer.user_id))
            assert found.output is not None
            opened |= {task.task_id for task in found.output.tasks}
            # Источник задачи — в её пространстве: workspace или личное владельца.
            spaces = {row.id: row.org_id for row in rows}
            for task, source in zip(found.output.tasks, found.sources, strict=True):
                assert (source.id, source.org_id) == (str(task.task_id), spaces[task.task_id])
        return opened

    def columns(row: ResourceRow) -> dict[str, object]:
        rows.append(row)
        return {"title": f"Задача {row.id}", "source": "meeting" if row.parent else "manual"}

    await assert_isolated(connection, TASK_RESOURCE, path, columns, PARENTS)
