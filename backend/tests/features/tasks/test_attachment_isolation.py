"""Downloads open to exactly those who may read the task, and no attachment outlives its task
whatever deletes it (the isolation kit, §7; ADR 0064 point 6)."""

import uuid

import pytest
from sqlalchemy import delete

from shosai.core.config.roles import ProcessRole
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.tasks.application.attachment_releases import AttachmentReleases
from shosai.features.tasks.infrastructure.task_records import TASK_RESOURCE, TaskRecord
from shosai.features.workspaces.contracts import Viewer
from tests.features.tasks.task_bench import PARENTS, TaskBench, task_columns
from tests.harness.connections import Connection
from tests.harness.database_access import ProcessShape, open_database_access, slot_urls
from tests.harness.run_slot import RunSlot
from tests.support.access_model import ResourceRow
from tests.support.isolation import assert_isolated

HELD = (
    "INSERT INTO held_objects (id, user_id, org_id, holder, object_key, filename, content_type,"
    " size_bytes) VALUES (%s, %s, %s, 'task_attachment', %s, 'a.pdf', 'application/pdf', 1)"
)
ATTACHMENT = (
    "INSERT INTO task_attachments (id, task_id, user_id, org_id, held_object_id, name,"
    " content_type, size_bytes, image, added_by)"
    " VALUES (%s, %s, %s, %s, %s, 'a.pdf', 'application/pdf', 1, false, %s)"
)


async def attach_each(
    connection: Connection, rows: list[ResourceRow]
) -> dict[uuid.UUID, uuid.UUID]:
    """An attachment held by files on every task of the world: the attachment of each task."""
    attached: dict[uuid.UUID, uuid.UUID] = {}
    async with connection.transaction():
        for row in rows:
            held, attachment = uuid.uuid4(), uuid.uuid4()
            key = f"u/{row.owner}/h/{held}"
            await connection.execute(HELD, (held, row.owner, row.org_id, key))
            params = (attachment, row.id, row.owner, row.org_id, held, row.owner)
            await connection.execute(ATTACHMENT, params)
            attached[row.id] = attachment
    return attached


@pytest.mark.isolation(resource="task")
async def test_an_attachment_downloads_for_exactly_those_who_may_read_its_task(
    task_bench: TaskBench, run_slot: RunSlot
) -> None:
    connection = run_slot.claimed.connections[Home.EU]
    rows: list[ResourceRow] = []
    attached: dict[uuid.UUID, uuid.UUID] = {}

    async def path(viewer: Viewer) -> set[uuid.UUID]:
        if not attached:
            attached.update(await attach_each(connection, rows))
        opened = set()
        for task_id, attachment in attached.items():
            link = f"/v1/tasks/{task_id}/attachments/{attachment}/download"
            if (await task_bench.call(viewer.user_id, "GET", link)).status_code == 200:
                opened.add(task_id)
        return opened

    def columns(row: ResourceRow) -> dict[str, object]:
        rows.append(row)
        return task_columns(row)

    await assert_isolated(connection, TASK_RESOURCE, path, columns, PARENTS)


async def test_a_task_deleted_past_tasks_routes_gives_its_attachments_back_by_the_tick(
    task_bench: TaskBench, run_slot: RunSlot
) -> None:
    me = uuid.uuid4()
    task = await task_bench.task(me)
    upload = await task_bench.files.uploaded(me, b"cascade", "application/pdf")
    await task_bench.call(me, "POST", f"/v1/tasks/{task}/attachments", {"upload_id": str(upload)})
    async with task_bench.homes.transactions.begin(TenancyScope(Home.EU, me)) as session:
        # Каскад мимо маршрутов tasks: так удаляют доска, аккаунт или пространство.
        await session.execute(delete(TaskRecord).where(TaskRecord.id == task))
    waiting = await task_bench.files.used(me)

    async with open_database_access(
        slot_urls(run_slot), ProcessShape(role=ProcessRole.WORKERS)
    ) as workers:
        releases = AttachmentReleases(workers.transactions, task_bench.ports)
        given = await releases.drain(Home.EU)
        again = await releases.drain(Home.EU)

    assert waiting == 7
    assert (given, again) == (1, 0)
    assert await task_bench.files.used(me) == 0
    assert not await task_bench.files.exists(f"u/{me}/h/{upload}")
