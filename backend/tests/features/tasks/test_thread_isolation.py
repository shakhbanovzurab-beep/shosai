"""A task's comments open to exactly those who may read the task (the isolation kit, §7)."""

import uuid

import pytest

from shosai.core.kernel.homes import Home
from shosai.features.tasks.infrastructure.task_records import TASK_RESOURCE
from shosai.features.workspaces.contracts import Viewer
from tests.features.tasks.task_bench import PARENTS, TaskBench, task_columns
from tests.harness.connections import Connection
from tests.harness.run_slot import RunSlot
from tests.support.access_model import ResourceRow
from tests.support.isolation import assert_isolated

COMMENT = (
    "INSERT INTO task_comments (id, task_id, user_id, org_id, author_user_id, body)"
    " VALUES (%s, %s, %s, %s, %s, 'Комментарий')"
)


async def comment_each(connection: Connection, rows: list[ResourceRow]) -> None:
    """A comment by its owner on every task of the world."""
    async with connection.transaction():
        for row in rows:
            params = (uuid.uuid4(), row.id, row.owner, row.org_id, row.owner)
            await connection.execute(COMMENT, params)


@pytest.mark.isolation(resource="task")
async def test_a_tasks_comments_open_to_exactly_those_who_may_read_it(
    task_bench: TaskBench, run_slot: RunSlot
) -> None:
    connection = run_slot.claimed.connections[Home.EU]
    rows: list[ResourceRow] = []
    commented: list[bool] = []

    async def path(viewer: Viewer) -> set[uuid.UUID]:
        if not commented:
            await comment_each(connection, rows)
            commented.append(True)
        opened = set()
        for row in rows:
            answer = await task_bench.call(viewer.user_id, "GET", f"/v1/tasks/{row.id}/comments")
            if answer.status_code == 200 and answer.json()["items"]:
                opened.add(row.id)
        return opened

    def columns(row: ResourceRow) -> dict[str, object]:
        rows.append(row)
        return task_columns(row)

    await assert_isolated(connection, TASK_RESOURCE, path, columns, PARENTS)
