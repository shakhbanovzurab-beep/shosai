"""A task's values open to exactly those who may read the task (the isolation kit, §7)."""

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

STICKER = "INSERT INTO stickers (id, user_id, kind, name) VALUES (%s, %s, 'text', 'Заметка')"
VALUE = (
    "INSERT INTO task_sticker_values (id, task_id, sticker_id, user_id, org_id, text)"
    " VALUES (%s, %s, %s, %s, %s, 'Срочно')"
)


async def value_each(connection: Connection, rows: list[ResourceRow]) -> None:
    """A value of its owner's own sticker on every task of the world."""
    async with connection.transaction():
        for row in rows:
            sticker = uuid.uuid4()
            await connection.execute(STICKER, (sticker, row.owner))
            await connection.execute(VALUE, (uuid.uuid4(), row.id, sticker, row.owner, row.org_id))


@pytest.mark.isolation(resource="task")
async def test_a_tasks_values_open_to_exactly_those_who_may_read_it(
    task_bench: TaskBench, run_slot: RunSlot
) -> None:
    connection = run_slot.claimed.connections[Home.EU]
    rows: list[ResourceRow] = []
    valued: list[bool] = []

    async def path(viewer: Viewer) -> set[uuid.UUID]:
        if not valued:
            await value_each(connection, rows)
            valued.append(True)
        opened = set()
        for row in rows:
            answer = await task_bench.call(viewer.user_id, "GET", f"/v1/tasks/{row.id}")
            if answer.status_code == 200 and answer.json()["other_values"]:
                opened.add(row.id)
        return opened

    def columns(row: ResourceRow) -> dict[str, object]:
        rows.append(row)
        return task_columns(row)

    await assert_isolated(connection, TASK_RESOURCE, path, columns, PARENTS)
