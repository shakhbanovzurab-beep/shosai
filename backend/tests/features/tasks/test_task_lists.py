"""Lists, Today and workspace tasks on the API: the access rules, the filters and the pages."""

import uuid
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from shosai.core.kernel.homes import Home
from shosai.features.tasks.infrastructure.task_records import TASK_RESOURCE
from shosai.features.workspaces.contracts import Viewer
from tests.features.tasks.task_bench import PARENTS, TaskBench, task_columns
from tests.harness.run_slot import RunSlot
from tests.support.access_model import MemberRow, ResourceRow, WorkspaceRow, World
from tests.support.isolation import assert_isolated, write_world


async def listed(bench: TaskBench, who: uuid.UUID, query: str = "") -> list[dict[str, object]]:
    """Every item of the person's list, page after page."""
    items: list[dict[str, object]] = []
    cursor = ""
    while True:
        answer = await bench.call(who, "GET", f"/v1/tasks?limit=3{query}{cursor}")
        assert answer.status_code == 200, answer.text
        items += answer.json()["items"]
        token = answer.json()["next_cursor"]
        if token is None:
            return items
        cursor = f"&cursor={token}"


@pytest.mark.isolation(resource="task")
async def test_the_list_shows_each_person_exactly_the_tasks_they_may_read(
    task_bench: TaskBench, run_slot: RunSlot
) -> None:
    async def path(viewer: Viewer) -> set[uuid.UUID]:
        return {uuid.UUID(str(item["id"])) for item in await listed(task_bench, viewer.user_id)}

    await assert_isolated(
        run_slot.claimed.connections[Home.EU], TASK_RESOURCE, path, task_columns, PARENTS
    )


@pytest.mark.isolation(resource="task")
async def test_a_task_opens_to_exactly_those_who_may_read_it(
    task_bench: TaskBench, run_slot: RunSlot
) -> None:
    ids: list[uuid.UUID] = []

    async def path(viewer: Viewer) -> set[uuid.UUID]:
        opened = set()
        for task_id in ids:
            answer = await task_bench.call(viewer.user_id, "GET", f"/v1/tasks/{task_id}")
            if answer.status_code == 200:
                opened.add(task_id)
        return opened

    def columns(row: ResourceRow) -> dict[str, object]:
        ids.append(row.id)
        return task_columns(row)

    await assert_isolated(
        run_slot.claimed.connections[Home.EU], TASK_RESOURCE, path, columns, PARENTS
    )


async def test_today_holds_the_persons_overdue_and_due_tasks_and_those_done_that_day(
    task_bench: TaskBench,
) -> None:
    me, other, org = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    task_bench.profiles.zones[me] = "Asia/Tokyo"
    today = datetime.now(ZoneInfo("Asia/Tokyo")).date()
    # Полночь в Токио — 15:00 UTC накануне: закрытая в 16:00 UTC вчера — уже «сегодня».
    tokyo_midnight = datetime.combine(today, datetime.min.time(), ZoneInfo("Asia/Tokyo"))
    shown = {
        await task_bench.task(me, title="Просрочено", due_on=today - timedelta(days=2)),
        await task_bench.task(me, title="Сегодня", due_on=today),
        await task_bench.task(
            me,
            title="Сделано сегодня",
            status="done",
            completed_at=tokyo_midnight + timedelta(hours=1),
        ),
    }
    await task_bench.task(me, title="Завтра", due_on=today + timedelta(days=1))
    await task_bench.task(me, title="Без срока")
    await task_bench.task(
        me, title="Вчера сделано", status="done", completed_at=tokyo_midnight - timedelta(hours=1)
    )
    await task_bench.task(other, title="Чужая", due_on=today)
    await task_bench.task(me, org, title="Пространства", due_on=today, assignee_user_id=me)

    answer = await task_bench.call(me, "GET", f"/v1/tasks/today?day={today.isoformat()}")
    by_zone = await task_bench.call(me, "GET", "/v1/tasks/today")

    assert {uuid.UUID(item["id"]) for item in answer.json()["items"]} == shown
    assert by_zone.json() == answer.json()


async def test_a_list_pages_by_due_day_with_no_day_last_and_filters_what_it_shows(
    task_bench: TaskBench,
) -> None:
    me = uuid.uuid4()
    soon, later = datetime.now(UTC).date(), datetime.now(UTC).date() + timedelta(days=9)
    ordered = [
        await task_bench.task(me, title="Срочно", due_on=soon),
        await task_bench.task(me, title="Потом", due_on=later),
        await task_bench.task(me, title="Отчёт без срока"),
        await task_bench.task(me, title="Сделано", status="done", completed_at=datetime.now(UTC)),
    ]

    everything = await listed(task_bench, me)
    open_only = await listed(task_bench, me, "&status=open")
    found = await listed(task_bench, me, "&q=%D0%BE%D1%82%D1%87%D1%91%D1%82")

    assert [uuid.UUID(str(i["id"])) for i in everything][:2] == ordered[:2]
    assert {uuid.UUID(str(i["id"])) for i in everything} == set(ordered)
    assert {uuid.UUID(str(i["id"])) for i in open_only} == set(ordered[:3])
    assert [i["title"] for i in found] == ["Отчёт без срока"]


async def test_a_workspace_task_is_made_assigned_and_deleted_by_the_rules(
    task_bench: TaskBench, run_slot: RunSlot
) -> None:
    org, other_org = uuid.uuid4(), uuid.uuid4()
    alice, bob, carol, dan, stranger = (uuid.uuid4() for _ in range(5))
    world = World(
        workspaces=[WorkspaceRow(org, "active"), WorkspaceRow(other_org, "active")],
        members=[
            MemberRow(uuid.uuid4(), org, alice, "owner", "active"),
            MemberRow(uuid.uuid4(), org, bob, "member", "active"),
            MemberRow(uuid.uuid4(), org, carol, "admin", "active"),
            MemberRow(uuid.uuid4(), org, dan, "member", "active"),
            MemberRow(uuid.uuid4(), other_org, bob, "owner", "active"),
        ],
    )
    await write_world(run_slot.claimed.connections[Home.EU], TASK_RESOURCE, world)
    task_bench.profiles.names_by_person[carol] = "Карина"

    made = await task_bench.call(
        bob, "POST", "/v1/tasks", {"title": "Общее", "workspace_id": str(org)}
    )
    task = made.json()["id"]
    outsider = await task_bench.call(
        stranger, "POST", "/v1/tasks", {"title": "Чужое", "workspace_id": str(org)}
    )
    wrong = await task_bench.call(bob, "PATCH", f"/v1/tasks/{task}", {"assignee_id": str(stranger)})
    named = await task_bench.call(bob, "PATCH", f"/v1/tasks/{task}", {"assignee_name": "Анна"})
    assigned = await task_bench.call(bob, "PATCH", f"/v1/tasks/{task}", {"assignee_id": str(carol)})
    seen_by_admin = await task_bench.call(carol, "GET", f"/v1/tasks/{task}")
    by_member = await task_bench.call(dan, "DELETE", f"/v1/tasks/{task}")
    elsewhere = await task_bench.task(bob, other_org)
    mixed = await task_bench.call(
        bob, "POST", "/v1/tasks/delete", {"task_ids": [task, str(elsewhere)]}
    )
    by_admin = await task_bench.call(carol, "DELETE", f"/v1/tasks/{task}")

    assert made.status_code == 201
    assert made.json()["space"]["workspace_id"] == str(org)
    assert (outsider.status_code, outsider.json()["error"]["code"]) == (404, "workspace_not_found")
    assert [wrong.status_code, named.status_code] == [422, 422]
    assert assigned.json()["assignee"] == {"user_id": str(carol), "name": "Карина"}
    assert seen_by_admin.json()["can_delete"] is True
    assert (by_member.status_code, by_member.json()["error"]["code"]) == (403, "task_not_deletable")
    assert (mixed.status_code, by_admin.status_code) == (422, 204)
    assert await task_bench.events(uuid.UUID(task)) == ["tasks.task.assigned", "tasks.task.deleted"]
