"""Leo's write tools over tasks (step 8): planned whole, approved, applied once on the plan."""

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

import pytest
from prometheus_client import CollectorRegistry
from pydantic import ValidationError
from sqlalchemy import select

from shosai.core.agent_tools.context import ToolContext
from shosai.core.agent_tools.events import ActionItemExecuted
from shosai.core.agent_tools.results import PlannedEffect, ToolErrorCode
from shosai.core.events.catalog import EventTypes
from shosai.core.events.outbox import EventOutbox
from shosai.core.idempotency.action_items import ActionItems
from shosai.core.idempotency.ledger import EffectLedger
from shosai.core.idempotency.metrics import EffectKeyMetrics
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.notes.module import NOTES
from shosai.features.tasks.application.task_edits import TaskEdits
from shosai.features.tasks.application.task_writes import TaskWrites
from shosai.features.tasks.channels.agent_task_changes import TaskChanges
from shosai.features.tasks.channels.agent_task_creates import TaskCreates
from shosai.features.tasks.channels.agent_write_tools import (
    WRITE_TOOLS,
    CompleteTask,
    CreateTasks,
    MoveTask,
    UpdateTask,
)
from shosai.features.tasks.contracts import ChatOrigin, Messenger
from shosai.features.tasks.domain.tasks import Priority
from shosai.features.tasks.infrastructure.task_records import TaskRecord
from shosai.features.tasks.module import TASKS
from shosai.features.workspaces.module import WORKSPACES
from tests.features.tasks.board_helpers import board, cards_of, column_ids, made
from tests.features.tasks.task_bench import HOME, TaskBench

OUTBOX = EventOutbox(
    EventTypes([*TASKS.events, *NOTES.events, *WORKSPACES.events, ActionItemExecuted])
)


@dataclass(frozen=True, slots=True)
class Writes:
    """The toolset's writes over the bench."""

    creates: TaskCreates
    changes: TaskChanges


def writes(bench: TaskBench) -> Writes:
    """The write tools' handlers on the bench's homes and ports."""
    transactions = bench.homes.transactions
    ledger = EffectLedger(EffectKeyMetrics(CollectorRegistry()))
    items = ActionItems(ledger, OUTBOX)
    task_writes = TaskWrites(transactions, bench.ports, (OUTBOX, ledger), bench.clock)
    edits = TaskEdits(transactions, bench.ports, OUTBOX, bench.clock)
    return Writes(
        TaskCreates(transactions, (task_writes, items), bench.clock),
        TaskChanges(transactions, bench.ports, (edits, items), bench.clock),
    )


def context(who: uuid.UUID) -> ToolContext:
    """A call of the person's run."""
    return ToolContext(
        TenancyScope(HOME, who), uuid.uuid4(), datetime.now(UTC) + timedelta(seconds=30)
    )


def planned(result: object) -> PlannedEffect:
    """The plan, which the test expects to be one."""
    assert isinstance(result, PlannedEffect), result
    return result


async def rows(bench: TaskBench, who: uuid.UUID, org: uuid.UUID | None = None) -> list[TaskRecord]:
    """The person's tasks in the space, oldest first."""
    async with bench.homes.transactions.begin(TenancyScope(HOME, who, org), read_only=True) as s:
        return list(
            await s.scalars(
                select(TaskRecord).where(TaskRecord.user_id == who).order_by(TaskRecord.created_at)
            )
        )


def test_the_toolset_holds_its_four_writes() -> None:
    assert [spec.name for spec in WRITE_TOOLS] == [
        "tasks.create", "tasks.update", "tasks.complete", "tasks.move",
    ]  # fmt: skip
    assert all(spec.provenance is None for spec in WRITE_TOOLS)


async def test_a_batch_is_made_whole_once_on_top_of_the_board(task_bench: TaskBench) -> None:
    me = uuid.uuid4()
    board_id = await made(task_bench, me)
    tools = writes(task_bench)
    args = CreateTasks.model_validate(
        {"tasks": [{"title": "Первая"}, {"title": "Вторая", "due_on": "2026-11-02"},
                   {"title": "Третья", "priority": "high"}],
         "board_id": board_id}
    )  # fmt: skip

    plan = planned(await tools.creates.plan(args, context(me)))
    preview = await tools.creates.preview(plan, context(me))
    first = await tools.creates.execute(plan, context(me), "item-1")
    again = await tools.creates.execute(plan, context(me), "item-1")

    assert (preview.key, preview.params["count"], preview.params["board"]) == (
        "agent.tasks.create_many",
        3,
        "Работа",
    )
    assert preview.params["first"] == "Первая"
    assert first.output is not None
    assert again.output == first.output
    made_rows = await rows(task_bench, me)
    assert [r.title for r in made_rows] == ["Первая", "Вторая", "Третья"]
    assert {r.created_by for r in made_rows} == {"leo"}
    assert cards_of(await board(task_bench, me, board_id), 0) == [
        str(t) for t in first.output.task_ids
    ]


async def test_one_invalid_task_stops_the_whole_batch(task_bench: TaskBench) -> None:
    me = uuid.uuid4()
    args = CreateTasks.model_validate(
        {"tasks": [{"title": "Хорошая"},
                   {"title": "Плохая", "due_on": "2026-11-02", "starts_on": "2026-11-05"}]}
    )  # fmt: skip

    refused = await writes(task_bench).creates.plan(args, context(me))

    assert not isinstance(refused, PlannedEffect)
    assert (refused.code, refused.params) == (
        ToolErrorCode.INVALID_ARGUMENTS,
        {"reason": "range_invalid"},
    )
    assert await rows(task_bench, me) == []


async def test_a_chat_source_comes_only_from_the_servers_plan(task_bench: TaskBench) -> None:
    me, org = uuid.uuid4(), uuid.uuid4()
    await task_bench.workspace(org, me)
    origin = ChatOrigin(
        None, Messenger.SLACK, "Release", None, datetime(2026, 10, 22, 9, tzinfo=UTC)
    )
    args = CreateTasks.model_validate({"tasks": [{"title": "Из чата"}], "workspace_id": str(org)})
    tools = writes(task_bench)

    plan = planned(await tools.creates.plan_from_chat(args, origin, context(me)))
    await tools.creates.execute(plan, context(me), "item-chat")

    (task,) = await rows(task_bench, me, org)
    assert (task.source, task.source_chat_title, task.created_by) == ("chat", "Release", "leo")
    with pytest.raises(ValidationError):
        CreateTasks.model_validate({"tasks": [{"title": "Из чата"}], "source": {"kind": "chat"}})


async def test_a_change_a_tick_and_a_move_act_on_the_planned_task_only(
    task_bench: TaskBench,
) -> None:
    me = uuid.uuid4()
    board_id = await made(task_bench, me)
    done = column_ids(await board(task_bench, me, board_id))[2]
    task = await task_bench.task(me, title="Отчёт", due_on=date(2026, 11, 2))
    other = await task_bench.task(me, title="Другая")
    tools = writes(task_bench)

    change = UpdateTask(task_id=task, due_on=None, priority=Priority.HIGH, description="Подробно")
    update = planned(await tools.changes.plan_update(change, context(me)))
    card = await tools.changes.preview_update(update, context(me))
    await tools.changes.execute_update(update, context(me), "item-u")
    move = planned(await tools.changes.plan_move(
        MoveTask(task_id=task, board_id=uuid.UUID(board_id), column_id=uuid.UUID(done)), context(me)
    ))  # fmt: skip
    moved = await tools.changes.execute_move(move, context(me), "item-m")
    reopen = planned(
        await tools.changes.plan_complete(CompleteTask(task_id=task, done=False), context(me))
    )
    reopened = await tools.changes.execute_complete(reopen, context(me), "item-c")
    reopen_card = await tools.changes.preview_complete(reopen, context(me))

    by_id = {r.id: r for r in await rows(task_bench, me)}
    assert by_id[task].due_on is None
    assert moved.output is not None
    assert moved.output.status == "done"
    assert reopened.output is not None
    assert reopened.output.status == "todo"
    assert (by_id[other].title, by_id[other].status) == ("Другая", "todo")
    assert (card.key, dict(card.params)) == ("agent.tasks.update", {
        "title": "Отчёт", "new_title": None, "due_on": "none", "starts_on": None,
        "priority": "high", "assignee": None, "details": "changed",
    })  # fmt: skip
    assert (reopen_card.key, reopen_card.params["title"]) == ("agent.tasks.reopen", "Отчёт")
    assert update.org_id is None


async def test_a_jira_card_and_a_task_out_of_reach_are_refused(task_bench: TaskBench) -> None:
    me = uuid.uuid4()
    jira = await task_bench.task(me, source="jira")
    foreign = await task_bench.task(uuid.uuid4())
    tools = writes(task_bench)

    on_jira = await tools.changes.plan_complete(CompleteTask(task_id=jira), context(me))
    out_of_reach = await tools.changes.plan_update(
        UpdateTask(task_id=foreign, title="Моё"), context(me)
    )

    assert not isinstance(on_jira, PlannedEffect)
    assert (on_jira.code, on_jira.params) == (ToolErrorCode.FAILED, {"reason": "jira_unsupported"})
    assert not isinstance(out_of_reach, PlannedEffect)
    assert out_of_reach.code is ToolErrorCode.NOT_FOUND


async def test_a_workspace_batch_names_only_its_members(task_bench: TaskBench) -> None:
    me, org = uuid.uuid4(), uuid.uuid4()
    await task_bench.workspace(org, me)
    stranger = str(uuid.uuid4())
    args = CreateTasks.model_validate(
        {"tasks": [{"title": "Кому-то", "assignee_id": stranger}], "workspace_id": str(org)}
    )
    outside = CreateTasks.model_validate(
        {"tasks": [{"title": "Чужое"}], "workspace_id": str(uuid.uuid4())}
    )

    refused = await writes(task_bench).creates.plan(args, context(me))
    elsewhere = await writes(task_bench).creates.plan(outside, context(me))

    assert not isinstance(refused, PlannedEffect)
    assert refused.code is ToolErrorCode.INVALID_ARGUMENTS
    assert not isinstance(elsewhere, PlannedEffect)
    assert elsewhere.code is ToolErrorCode.NOT_FOUND
