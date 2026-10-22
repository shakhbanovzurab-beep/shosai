"""Tasks' tables: the `task` resource obeys the access rules; the database keeps the rules."""

import uuid
from collections.abc import Mapping
from datetime import UTC, datetime

import psycopg
import pytest
from psycopg import sql
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError

from shosai.core.events.catalog import EventTypes
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.notes.infrastructure.meeting_records import MEETING_RESOURCE
from shosai.features.tasks.infrastructure.board_records import BoardRecord
from shosai.features.tasks.infrastructure.task_records import TASK_RESOURCE, TaskRecord
from shosai.features.workspaces.application.access_policy import WorkspaceAccessPolicy
from shosai.features.workspaces.contracts import Viewer
from shosai.features.workspaces.infrastructure.audit_log import WorkspaceAuditLog
from shosai.features.workspaces.module import WORKSPACES
from tests.harness.connections import Connection, fetch_value
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot
from tests.support.access_model import (
    GrantRow,
    MemberRow,
    ResourceRow,
    ShareRow,
    WorkspaceRow,
    World,
)
from tests.support.isolation import assert_isolated, write_world

MEETING_COLUMNS = {"title": "Созвон", "started_at": datetime.now(UTC)}
PARENTS = {"meeting": (MEETING_RESOURCE, MEETING_COLUMNS)}


def policy() -> WorkspaceAccessPolicy:
    return WorkspaceAccessPolicy(
        EventOutbox(EventTypes(list(WORKSPACES.events))),
        WorkspaceAuditLog(),
        (MEETING_RESOURCE, TASK_RESOURCE),
    )


def task_columns(row: ResourceRow) -> dict[str, object]:
    """A meeting's task names its source; a task without a parent is a hand-made one."""
    return {"title": "Отправить договор", "source": "meeting" if row.parent else "manual"}


async def readable_tasks(homes: DatabaseAccess, home: Home, viewer: Viewer) -> set[uuid.UUID]:
    scope = TenancyScope(home, viewer.user_id)
    async with homes.transactions.begin(scope, read_only=True) as session:
        query = select(TaskRecord.id).where(policy().readable(TASK_RESOURCE, viewer))
        return set(await session.scalars(query))


@pytest.mark.isolation(resource="task")
@pytest.mark.parametrize("home", list(Home))
async def test_the_tasks_a_person_sees_obey_the_access_rules(
    homes: DatabaseAccess, run_slot: RunSlot, home: Home
) -> None:
    async def path(viewer: Viewer) -> set[uuid.UUID]:
        return await readable_tasks(homes, home, viewer)

    await assert_isolated(
        run_slot.claimed.connections[home], TASK_RESOURCE, path, task_columns, PARENTS
    )


async def test_a_meetings_task_follows_the_meetings_audience_in_the_next_statement(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    connection = run_slot.claimed.connections[Home.RU]
    org, alice, bob = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    alice_seat, bob_seat, meeting, task = (uuid.uuid4() for _ in range(4))
    world = World(
        workspaces=[WorkspaceRow(org, "active")],
        members=[
            MemberRow(alice_seat, org, alice, "owner", "active"),
            MemberRow(bob_seat, org, bob, "member", "active"),
        ],
        rows=[
            ResourceRow(meeting, "meeting", alice, None, None),
            ResourceRow(task, "task", alice, org, "owner", parent=meeting),
        ],
        shares=[ShareRow("meeting", meeting, org, "selected", alice_seat, "meeting", meeting)],
        grants=[GrantRow(org, "meeting", meeting, "member", bob_seat)],
    )
    await write_world(connection, TASK_RESOURCE, world, task_columns, PARENTS)

    seen = [task in await readable_tasks(homes, Home.RU, Viewer(bob))]
    await connection.execute("DELETE FROM resource_grants WHERE resource_id = %s", (meeting,))
    seen.append(task in await readable_tasks(homes, Home.RU, Viewer(bob)))
    await connection.execute("UPDATE tasks SET assignee_user_id = %s WHERE id = %s", (bob, task))
    seen.append(task in await readable_tasks(homes, Home.RU, Viewer(bob)))
    await connection.execute(
        "DELETE FROM workspace_meeting_shares WHERE session_id = %s", (meeting,)
    )
    seen.append(task in await readable_tasks(homes, Home.RU, Viewer(alice)))

    assert seen == [True, False, True, True]


async def _board_with_columns(connection: Connection, user_id: uuid.UUID) -> list[uuid.UUID]:
    board, todo, done = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    await connection.execute(
        "INSERT INTO boards (id, user_id, name, icon) VALUES (%s, %s, 'Работа', 'briefcase')",
        (board, user_id),
    )
    await connection.execute(
        "INSERT INTO board_columns (id, board_id, user_id, title, kind, position)"
        " VALUES (%s, %s, %s, 'К работе', 'todo', 0), (%s, %s, %s, 'Готово', 'done', 1)",
        (todo, board, user_id, done, board, user_id),
    )
    return [board, todo, done]


async def _task(
    connection: Connection, user_id: uuid.UUID, fields: Mapping[str, object] | None = None
) -> uuid.UUID:
    """A task of the person written by the tables' owner, with these columns besides."""
    task = uuid.uuid4()
    values = {"id": task, "user_id": user_id, "title": "Позвонить", **(fields or {})}
    statement = sql.SQL("INSERT INTO tasks ({}) VALUES ({})").format(
        sql.SQL(", ").join(sql.Identifier(name) for name in values),
        sql.SQL(", ").join(sql.Placeholder() for _ in values),
    )
    await connection.execute(statement, tuple(values.values()))
    return task


@pytest.mark.parametrize(
    "fields",
    [
        {"status": "done"},
        {"completed_at": datetime.now(UTC)},
        {"assignee_user_id": uuid.uuid4()},
        {"project_id": uuid.uuid4()},
        {"source": "meeting"},
        {"source_meeting_id": uuid.uuid4()},
        {"priority": "urgent"},
        {"assignee_name": ""},
        {"title": "я" * 201},
    ],
)
async def test_the_database_refuses_a_task_breaking_its_rules(
    run_slot: RunSlot, fields: dict[str, object]
) -> None:
    connection = run_slot.claimed.connections[Home.EU]

    with pytest.raises(psycopg.errors.CheckViolation):
        await _task(connection, uuid.uuid4(), fields)


async def test_one_task_per_action_item_of_a_meeting(run_slot: RunSlot) -> None:
    connection = run_slot.claimed.connections[Home.RU]
    owner, meeting, finding = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    fields = {"source": "meeting", "source_meeting_id": meeting, "source_finding_id": finding}
    await _task(connection, owner, fields)

    with pytest.raises(psycopg.errors.UniqueViolation):
        await _task(connection, owner, fields)


async def test_a_card_sits_in_a_column_of_its_own_board(run_slot: RunSlot) -> None:
    connection = run_slot.claimed.connections[Home.RU]
    person = uuid.uuid4()
    board, todo, _ = await _board_with_columns(connection, person)
    _, other_todo, _ = await _board_with_columns(connection, person)
    task = await _task(connection, person)
    placement = (
        "INSERT INTO task_placements (user_id, task_id, board_id, column_id, rank)"
        " VALUES (%s, %s, %s, %s, 'V')"
    )
    await connection.execute(placement, (person, task, board, todo))

    stray = await _task(connection, person)
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        await connection.execute(placement, (person, stray, board, other_todo))
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        await connection.execute("DELETE FROM board_columns WHERE id = %s", (todo,))
    await connection.execute("DELETE FROM boards WHERE id = %s", (board,))
    assert await _count(connection, "task_placements", person) == 0
    assert await _count(connection, "board_columns", person) == 2


async def test_two_cards_of_a_column_never_share_a_place_at_commit(run_slot: RunSlot) -> None:
    connection = run_slot.claimed.connections[Home.EU]
    person = uuid.uuid4()
    board, todo, _ = await _board_with_columns(connection, person)
    first, second = await _task(connection, person), await _task(connection, person)
    placement = (
        "INSERT INTO task_placements (user_id, task_id, board_id, column_id, rank)"
        " VALUES (%s, %s, %s, %s, %s)"
    )

    async def both_at_one_place() -> None:
        async with connection.transaction():
            await connection.execute(placement, (person, first, board, todo, "V"))
            # Внутри транзакции ключи могут совпасть: перераскладка пишет колонку целиком.
            await connection.execute(placement, (person, second, board, todo, "V"))

    with pytest.raises(psycopg.errors.UniqueViolation):
        await both_at_one_place()
    with pytest.raises(psycopg.errors.CheckViolation):
        await connection.execute(placement, (person, first, board, todo, "V0"))


async def test_a_person_never_reads_or_writes_anothers_board(homes: DatabaseAccess) -> None:
    owner, other = uuid.uuid4(), uuid.uuid4()
    board = BoardRecord(id=uuid.uuid4(), user_id=owner, name="Дом", icon="home")
    async with homes.transactions.begin(TenancyScope(Home.RU, owner)) as session:
        session.add(board)
    async with homes.transactions.begin(TenancyScope(Home.RU, other), read_only=True) as session:
        assert (await session.scalars(select(BoardRecord.id))).all() == []

    with pytest.raises(DBAPIError, match="row-level security"):
        async with homes.transactions.begin(TenancyScope(Home.RU, other)) as session:
            session.add(BoardRecord(id=uuid.uuid4(), user_id=owner, name="Чужая", icon="home"))


async def _count(connection: Connection, table: str, person: uuid.UUID) -> int:
    query = sql.SQL("SELECT count(*) FROM {} WHERE user_id = %s").format(sql.Identifier(table))
    value = await fetch_value(connection, query, (person,))
    assert isinstance(value, int)
    return value
