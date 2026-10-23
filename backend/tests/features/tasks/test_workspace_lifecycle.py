"""Tasks follow a member's departure and a deleted project (tasks plan step 6, nfr-16).

The consumers run as the delivery runs them — in the scope `scope_of_departure` and
`scope_of_workspace` name — on a workspace whose member has just left.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.tasks.application.workspace_lifecycle import (
    clear_project,
    follow_departure,
    scope_of_departure,
    scope_of_workspace,
)
from shosai.features.tasks.channels.subscriptions import subscriptions
from shosai.features.tasks.infrastructure.task_records import TaskRecord
from shosai.features.tasks.infrastructure.thread_records import TaskSubtaskRecord
from shosai.features.workspaces.contracts.events import MemberRemoved, ProjectDeleted
from shosai.features.workspaces.domain.memberships import RemovalReason
from tests.features.tasks.board_helpers import board, cards_of, column_ids, made
from tests.features.tasks.task_bench import HOME, TaskBench

NOW = datetime(2026, 10, 23, 12, tzinfo=UTC)
REMOVE = (
    "UPDATE memberships SET state = %s, removed_at = now(), removal_reason = 'removed_by_admin'"
    " WHERE org_id = %s AND user_id = %s"
)


def departure(org: uuid.UUID, member: uuid.UUID, successor: uuid.UUID | None) -> MemberRemoved:
    """The event workspaces writes when the member leaves."""
    return MemberRemoved(
        org_id=org, user_id=member, membership_id=uuid.uuid4(),
        reason=RemovalReason.REMOVED_BY_ADMIN, successor_user_id=successor,
    )  # fmt: skip


async def deliver(bench: TaskBench, event: MemberRemoved, actor: uuid.UUID) -> None:
    """The departure applied as the delivery applies it, in the scope it names."""
    scope = scope_of_departure(event, TenancyScope(HOME, actor, event.org_id))
    async with bench.homes.transactions.begin(scope) as session:
        await follow_departure(session, bench.ports, event, NOW)


async def facts(
    bench: TaskBench, task: uuid.UUID, org: uuid.UUID, owner: uuid.UUID
) -> tuple[object, ...]:
    """The task's owner, assignee and version, read in the workspace."""
    async with bench.homes.transactions.begin(TenancyScope(HOME, owner, org), read_only=True) as s:
        row = (
            await s.execute(
                select(TaskRecord.user_id, TaskRecord.assignee_user_id).where(TaskRecord.id == task)
            )
        ).one()
        lines = set(
            await s.scalars(
                select(TaskSubtaskRecord.user_id).where(TaskSubtaskRecord.task_id == task)
            )
        )
    return row[0], row[1], lines


async def test_a_departed_member_leaves_no_task_of_the_workspace_in_their_hands(
    task_bench: TaskBench,
) -> None:
    owner, member, org = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    await task_bench.workspace(org, owner, member)
    theirs = await task_bench.task(member, org, assignee_user_id=member)
    given = await task_bench.task(owner, org, assignee_user_id=member)
    finished = await task_bench.task(
        member, org, assignee_user_id=member, status="done", completed_at=NOW
    )
    personal = await task_bench.task(member)
    async with task_bench.homes.transactions.begin(TenancyScope(HOME, member, org)) as session:
        session.add(TaskSubtaskRecord(id=uuid.uuid4(), task_id=theirs, user_id=member, org_id=org,
                                      title="Пункт", rank="V"))  # fmt: skip
    board_id = await made(task_bench, member)
    todo = uuid.UUID(column_ids(await board(task_bench, member, board_id))[0])
    for task in (theirs, given, personal):
        await task_bench.place_in(member, task, (uuid.UUID(board_id), todo))
    before = await task_bench.revision(member, uuid.UUID(board_id))
    await task_bench.connection.execute(REMOVE, ("removed", org, member))

    event = departure(org, member, owner)
    await deliver(task_bench, event, owner)
    after = await task_bench.revision(member, uuid.UUID(board_id))
    await deliver(task_bench, event, owner)

    assert await facts(task_bench, theirs, org, owner) == (owner, None, {owner})
    assert await facts(task_bench, given, org, owner) == (owner, None, set())
    assert await facts(task_bench, finished, org, owner) == (owner, member, set())
    assert cards_of(await board(task_bench, member, board_id), 0) == [str(personal)]
    assert (await task_bench.call(member, "GET", f"/v1/tasks/{theirs}")).status_code == 404
    assert after == before + 1
    assert await task_bench.revision(member, uuid.UUID(board_id)) == after


async def test_a_member_back_in_the_workspace_keeps_their_tasks(task_bench: TaskBench) -> None:
    owner, member, org = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    await task_bench.workspace(org, owner, member)
    theirs = await task_bench.task(member, org, assignee_user_id=member)

    await deliver(task_bench, departure(org, member, owner), owner)

    assert await facts(task_bench, theirs, org, owner) == (member, member, set())


async def test_without_a_standing_owner_the_tasks_stay_with_the_departed(
    task_bench: TaskBench,
) -> None:
    owner, member, org = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    await task_bench.workspace(org, owner, member)
    theirs = await task_bench.task(member, org, assignee_user_id=member)
    await task_bench.connection.execute(REMOVE, ("removed", org, member))

    await deliver(task_bench, departure(org, member, None), owner)

    assert await facts(task_bench, theirs, org, owner) == (member, None, set())


async def test_a_deleted_project_leaves_its_tasks_without_it(task_bench: TaskBench) -> None:
    owner, org, project = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    await task_bench.workspace(org, owner)
    inside = await task_bench.task(owner, org, project_id=project)
    other = await task_bench.task(owner, org, project_id=uuid.uuid4())
    event = ProjectDeleted(org_id=org, project_id=project)

    scope = scope_of_workspace(event, TenancyScope(HOME, owner))
    async with task_bench.homes.transactions.begin(scope) as session:
        await clear_project(session, event, NOW)
    async with task_bench.homes.transactions.begin(scope, read_only=True) as session:
        rows = await session.execute(
            select(TaskRecord.id, TaskRecord.project_id).where(TaskRecord.id.in_([inside, other]))
        )
        projects = {task_id: project_id for task_id, project_id in rows}

    assert projects[inside] is None
    assert projects[other] is not None


async def test_the_consumers_keep_their_names_and_scopes(task_bench: TaskBench) -> None:
    named = {s.consumer: s.scope for s in subscriptions(task_bench.ports)}

    assert named == {
        "tasks.follow_departure": scope_of_departure,
        "tasks.forget_project": scope_of_workspace,
    }


async def test_nothing_of_a_deleted_workspace_is_left_to_read(task_bench: TaskBench) -> None:
    owner, org = uuid.uuid4(), uuid.uuid4()
    await task_bench.workspace(org, owner)
    task = await task_bench.task(owner, org)
    board_id = await made(task_bench, owner)
    todo = uuid.UUID(column_ids(await board(task_bench, owner, board_id))[0])
    await task_bench.place_in(owner, task, (uuid.UUID(board_id), todo))

    await task_bench.connection.execute("DELETE FROM organizations WHERE id = %s", (org,))
    read = await task_bench.call(owner, "GET", f"/v1/tasks/{task}")
    listed = (await task_bench.call(owner, "GET", "/v1/tasks")).json()["items"]

    assert read.status_code == 404
    assert listed == []
    assert cards_of(await board(task_bench, owner, board_id), 0) == []
