"""Leo's `boards` toolset: boards and columns planned, carded, applied once (tasks plan §3.3)."""

import uuid
from datetime import UTC, datetime, timedelta

from prometheus_client import CollectorRegistry
from sqlalchemy import select

from shosai.core.agent_tools.context import ToolContext
from shosai.core.agent_tools.events import ActionItemExecuted
from shosai.core.agent_tools.results import PlannedEffect, ToolError, ToolErrorCode
from shosai.core.events.catalog import EventTypes
from shosai.core.events.outbox import EventOutbox
from shosai.core.idempotency.action_items import ActionItems
from shosai.core.idempotency.ledger import EffectLedger
from shosai.core.idempotency.metrics import EffectKeyMetrics
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.tasks.application.attachment_releases import AttachmentReleases
from shosai.features.tasks.application.board_reads import BoardReads
from shosai.features.tasks.channels.agent_board_specs import (
    BOARD_TOOLS,
    AddColumn,
    BoardRef,
    ChooseIncoming,
    ColumnRef,
    CreateBoard,
    NoArguments,
    UpdateBoard,
    UpdateColumn,
)
from shosai.features.tasks.channels.agent_board_tools import BoardTools
from shosai.features.tasks.channels.agent_board_work import BoardWork
from shosai.features.tasks.channels.agent_column_tools import ColumnTools
from shosai.features.tasks.domain.board_fields import Color
from shosai.features.tasks.domain.tasks import TaskStatus
from shosai.features.tasks.infrastructure.task_records import TaskRecord
from shosai.features.tasks.module import TASKS
from tests.features.tasks.board_helpers import board, cards_of, column_ids, made
from tests.features.tasks.task_bench import HOME, TaskBench

OUTBOX = EventOutbox(EventTypes([*TASKS.events, ActionItemExecuted]))


def tools(bench: TaskBench) -> tuple[BoardTools, ColumnTools]:
    """The toolset's handlers on the bench's homes and ports."""
    transactions = bench.homes.transactions
    ledger = EffectLedger(EffectKeyMetrics(CollectorRegistry()))
    work = BoardWork(transactions, ActionItems(ledger, OUTBOX), OUTBOX)
    services = (
        BoardReads(transactions, bench.ports), bench.ports,
        AttachmentReleases(transactions, bench.ports),
    )  # fmt: skip
    return BoardTools(work, services, bench.clock), ColumnTools(work, bench.clock)


def context(who: uuid.UUID) -> ToolContext:
    """A call of the person's run."""
    return ToolContext(
        TenancyScope(HOME, who), uuid.uuid4(), datetime.now(UTC) + timedelta(seconds=30)
    )


def planned(result: PlannedEffect | ToolError) -> PlannedEffect:
    """The plan, which the test expects to be one."""
    assert isinstance(result, PlannedEffect), result
    return result


def refused(result: PlannedEffect | ToolError) -> tuple[ToolErrorCode, object]:
    """The refusal's code and reason, which the test expects."""
    assert isinstance(result, ToolError), result
    return result.code, result.params.get("reason")


def test_the_toolset_holds_a_list_and_seven_writes() -> None:
    assert [spec.name for spec in BOARD_TOOLS] == [
        "boards.list", "boards.create", "boards.update", "boards.delete", "boards.add_column",
        "boards.update_column", "boards.delete_column", "boards.set_incoming",
    ]  # fmt: skip
    assert {spec.toolset for spec in BOARD_TOOLS} == {"boards"}
    assert all(spec.provenance is None for spec in BOARD_TOOLS)


async def test_a_board_is_made_once_from_its_template_or_its_own_columns(
    task_bench: TaskBench,
) -> None:
    me = uuid.uuid4()
    boards, _ = tools(task_bench)
    simple = planned(await boards.plan_create(CreateBoard(name=" Дом "), context(me)))
    own = planned(await boards.plan_create(CreateBoard.model_validate({
        "name": "Ремонт", "columns": [
            {"title": "Купить", "kind": "todo"}, {"title": "Делаем", "kind": "in_progress"},
            {"title": "Проверить", "kind": "in_progress"}, {"title": "Готово", "kind": "done"},
        ],
    }), context(me)))  # fmt: skip
    card = await boards.preview_create(own, context(me))
    first = await boards.create(simple, context(me), "item-1")
    again = await boards.create(simple, context(me), "item-1")
    custom = await boards.create(own, context(me), "item-2")
    listed = await boards.listed(NoArguments(), context(me))

    assert first.output is not None
    assert again.output == first.output
    assert len(first.output.columns) == 3
    assert custom.output is not None
    detail = await board(task_bench, me, str(custom.output.board_id))
    assert [c["title"] for c in detail["columns"]] == ["Купить", "Делаем", "Проверить", "Готово"]
    assert (card.key, dict(card.params)) == (
        "agent.boards.create", {"name": "Ремонт", "columns": "Купить, Делаем, Проверить, Готово"}
    )  # fmt: skip
    assert listed.output is not None
    assert [line.name for line in listed.output.boards] == ["Дом", "Ремонт"]


async def test_a_board_without_a_column_of_every_kind_is_refused(task_bench: TaskBench) -> None:
    me = uuid.uuid4()
    boards, _ = tools(task_bench)
    args = CreateBoard.model_validate(
        {"name": "Список", "columns": [{"title": "Сделать", "kind": "todo"}]}
    )

    assert refused(await boards.plan_create(args, context(me))) == (
        ToolErrorCode.INVALID_ARGUMENTS, "board_kinds_missing",
    )  # fmt: skip


async def test_a_rename_and_an_incoming_choice_act_on_the_persons_board_only(
    task_bench: TaskBench,
) -> None:
    me, stranger = uuid.uuid4(), uuid.uuid4()
    board_id = uuid.UUID(await made(task_bench, me))
    boards, _ = tools(task_bench)

    rename = planned(
        await boards.plan_update(UpdateBoard(board_id=board_id, name="Проект"), context(me))
    )
    card = await boards.preview_update(rename, context(me))
    await boards.update(rename, context(me), "item-r")
    choose = planned(await boards.plan_incoming(ChooseIncoming(board_id=board_id), context(me)))
    chosen_card = await boards.preview_incoming(choose, context(me))
    await boards.incoming(choose, context(me), "item-i")
    none_card = await boards.preview_incoming(
        planned(await boards.plan_incoming(ChooseIncoming(board_id=None), context(me))), context(me)
    )
    listed = await boards.listed(NoArguments(), context(me))
    foreign = await boards.plan_update(
        UpdateBoard(board_id=board_id, name="Чужая"), context(stranger)
    )

    assert (card.key, dict(card.params)) == (
        "agent.boards.update",
        {"name": "Работа", "new_name": "Проект"},
    )
    assert (chosen_card.key, dict(chosen_card.params)) == (
        "agent.boards.incoming",
        {"board": "Проект"},
    )
    assert none_card.key == "agent.boards.no_incoming"
    assert listed.output is not None
    assert [(line.name, line.incoming) for line in listed.output.boards] == [("Проект", True)]
    assert refused(foreign) == (ToolErrorCode.NOT_FOUND, None)


async def test_a_deleted_board_takes_its_hand_made_tasks_once(task_bench: TaskBench) -> None:
    me = uuid.uuid4()
    board_id = uuid.UUID(await made(task_bench, me))
    first = uuid.UUID(column_ids(await board(task_bench, me, str(board_id)))[0])
    task = await task_bench.task(me, title="Сделать")
    await task_bench.place_in(me, task, (board_id, first))
    boards, _ = tools(task_bench)

    plan = planned(await boards.plan_delete(BoardRef(board_id=board_id), context(me)))
    card = await boards.preview_delete(plan, context(me))
    gone = await boards.delete(plan, context(me), "item-d")
    again = await boards.delete(plan, context(me), "item-d")
    async with task_bench.homes.transactions.begin(TenancyScope(HOME, me), read_only=True) as s:
        left = list(await s.scalars(select(TaskRecord.id).where(TaskRecord.user_id == me)))

    assert (card.key, dict(card.params)) == ("agent.boards.delete", {"name": "Работа", "tasks": 1})
    assert gone.output is not None
    assert again.output == gone.output
    assert left == []
    assert refused(await boards.plan_delete(BoardRef(board_id=board_id), context(me))) == (
        ToolErrorCode.NOT_FOUND, None,
    )  # fmt: skip


async def test_columns_are_added_changed_and_removed_with_their_cards(
    task_bench: TaskBench,
) -> None:
    me = uuid.uuid4()
    board_id = uuid.UUID(await made(task_bench, me))
    first = uuid.UUID(column_ids(await board(task_bench, me, str(board_id)))[0])
    task = await task_bench.task(me, title="Сделать")
    await task_bench.place_in(me, task, (board_id, first))
    _, columns = tools(task_bench)

    add = planned(await columns.plan_add(AddColumn(
        board_id=board_id, title="Входящие", kind=TaskStatus.TODO, position=0, color=Color.RED,
    ), context(me)))  # fmt: skip
    add_card = await columns.preview_add(add, context(me))
    added = await columns.add(add, context(me), "item-a")
    assert added.output is not None
    column_id = added.output.column_id
    recolour = planned(await columns.plan_update(UpdateColumn.model_validate(
        {"board_id": str(board_id), "column_id": str(column_id), "title": "Новые", "color": None}
    ), context(me)))  # fmt: skip
    update_card = await columns.preview_update(recolour, context(me))
    await columns.update(recolour, context(me), "item-u")
    remove = planned(
        await columns.plan_delete(ColumnRef(board_id=board_id, column_id=first), context(me))
    )
    remove_card = await columns.preview_delete(remove, context(me))
    await columns.delete(remove, context(me), "item-x")
    detail = await board(task_bench, me, str(board_id))

    assert (add_card.key, dict(add_card.params)) == (
        "agent.boards.add_column", {"title": "Входящие", "board": "Работа", "kind": "todo"}
    )  # fmt: skip
    assert update_card.params["new_title"] == "Новые"
    assert (remove_card.key, remove_card.params["moved_to"]) == (
        "agent.boards.delete_column",
        "Новые",
    )
    assert detail["columns"][0]["title"] == "Новые"
    assert detail["columns"][0]["color"] is None
    assert len(detail["columns"]) == 3
    assert cards_of(detail, 0) == [str(task)]


async def test_the_last_column_of_a_kind_and_a_full_board_are_refused(
    task_bench: TaskBench,
) -> None:
    me = uuid.uuid4()
    board_id = uuid.UUID(await made(task_bench, me))
    done = uuid.UUID(column_ids(await board(task_bench, me, str(board_id)))[2])
    _, columns = tools(task_bench)
    for position in range(17):
        new = AddColumn(board_id=board_id, title=f"К{position}", kind=TaskStatus.TODO)
        await columns.add(
            planned(await columns.plan_add(new, context(me))), context(me), f"i{position}"
        )

    last = await columns.plan_delete(ColumnRef(board_id=board_id, column_id=done), context(me))
    full = await columns.plan_add(
        AddColumn(board_id=board_id, title="Лишняя", kind=TaskStatus.DONE), context(me)
    )

    assert refused(last) == (ToolErrorCode.INVALID_ARGUMENTS, "last_column_of_kind")
    assert refused(full) == (ToolErrorCode.LIMIT_REACHED, "board_columns_full")
