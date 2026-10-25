"""Another slice reads the person's boards through `BoardReader`: Leo's page context does."""

import uuid

from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.tasks.application.board_facts import BoardFactsReader
from tests.features.tasks.board_helpers import made
from tests.features.tasks.task_bench import HOME, TaskBench


async def test_another_slice_reads_only_the_persons_boards_oldest_first(
    task_bench: TaskBench,
) -> None:
    me, other = uuid.uuid4(), uuid.uuid4()
    first = uuid.UUID(await made(task_bench, me))
    second = uuid.UUID(await made(task_bench, me))
    theirs = uuid.UUID(await made(task_bench, other))
    reader = BoardFactsReader()

    scope = TenancyScope(HOME, me)
    async with task_bench.homes.transactions.begin(scope, read_only=True) as session:
        boards = await reader.boards(session, me)
        mine = await reader.exists(session, me, first)
        foreign = await reader.exists(session, me, theirs)

    assert [(board.board_id, board.name, board.synced_with_jira) for board in boards] == [
        (first, "Работа", False),
        (second, "Работа", False),
    ]
    assert (mine, foreign) == (True, False)
