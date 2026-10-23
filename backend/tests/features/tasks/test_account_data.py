"""Tasks' part of a person's export, transfer and erasure (ADR 0045 point 7)."""

import uuid
from collections.abc import Collection
from dataclasses import dataclass, field
from typing import cast

from sqlalchemy import select

from shosai.core.account_data.handlers import AccountRef
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.files.contracts.held_objects import HELD_OBJECTS, HeldObjects
from shosai.features.tasks.application.account_data import TasksAccountData
from shosai.features.tasks.infrastructure.attachment_records import TaskAttachmentRecord
from shosai.features.tasks.infrastructure.board_records import (
    BoardColumnRecord,
    BoardRecord,
    TaskPlacementRecord,
    TaskSettingsRecord,
)
from shosai.features.tasks.infrastructure.task_records import MeetingTaskSetRecord, TaskRecord
from shosai.features.tasks.infrastructure.thread_records import (
    TaskCommentRecord,
    TaskSubtaskRecord,
)
from tests.harness.database_access import DatabaseAccess

HELD = uuid.uuid4()


async def seed(homes: DatabaseAccess, person: uuid.UUID, org: uuid.UUID) -> tuple[uuid.UUID, ...]:
    """A board with a personal and a workspace task, each with a line and a comment, a set and
    the settings."""
    board, column, own, shared = (uuid.uuid4() for _ in range(4))
    async with homes.transactions.begin(TenancyScope(Home.RU, person, org)) as session:
        session.add(
            TaskRecord(id=shared, user_id=person, org_id=org, access="organization", title="Общее")
        )
    async with homes.transactions.begin(TenancyScope(Home.RU, person)) as session:
        session.add(BoardRecord(id=board, user_id=person, name="Работа", icon="briefcase"))
        session.add(TaskRecord(id=own, user_id=person, title="Своё", status="todo"))
        session.add(MeetingTaskSetRecord(meeting_id=uuid.uuid4(), user_id=person, revision=1))
        await session.flush()
        session.add(
            BoardColumnRecord(
                id=column, board_id=board, user_id=person, title="К работе", kind="todo", position=0
            )
        )
        await session.flush()
        for task, rank in ((own, "V"), (shared, "k")):
            session.add(
                TaskPlacementRecord(
                    user_id=person, task_id=task, board_id=board, column_id=column, rank=rank
                )
            )
        session.add(TaskSettingsRecord(user_id=person, incoming_board_id=board))
    for task, org_id in ((own, None), (shared, org)):
        async with homes.transactions.begin(TenancyScope(Home.RU, person, org_id)) as session:
            session.add(
                TaskSubtaskRecord(
                    id=uuid.uuid4(), task_id=task, user_id=person, org_id=org_id, title="Пункт",
                    rank="V",
                )
            )  # fmt: skip
            session.add(
                TaskCommentRecord(
                    id=uuid.uuid4(), task_id=task, user_id=person, org_id=org_id,
                    author_user_id=person, body="Комментарий",
                )
            )  # fmt: skip
            if org_id is None:
                session.add(
                    TaskAttachmentRecord(
                        id=uuid.uuid4(), task_id=task, user_id=person, name="Схема.png",
                        content_type="image/png", size_bytes=8, image=True, added_by=person,
                        held_object_id=HELD,
                    )
                )  # fmt: skip
    return own, shared


@dataclass
class Released:
    """Files' held objects as the test sees them: what tasks gave back."""

    ids: list[uuid.UUID] = field(default_factory=list)

    async def release(self, session: object, held_ids: Collection[uuid.UUID]) -> tuple[str, ...]:
        """Note the ids; nothing to discard."""
        del session
        self.ids += held_ids
        return ()

    async def discard(self, home: Home, keys: Collection[str]) -> None:
        """Nothing was released to discard."""
        del home, keys


async def test_export_transfer_and_erasure_leave_a_workspaces_tasks_with_it(
    homes: DatabaseAccess,
) -> None:
    person, org = uuid.uuid4(), uuid.uuid4()
    own, shared = await seed(homes, person, org)
    released = Released()
    ports = PortDirectory()
    ports.install([HELD_OBJECTS.bind(cast("HeldObjects", released))])
    handler = TasksAccountData(homes.transactions, ports)
    russian, european = AccountRef(person, Home.RU), AccountRef(person, Home.EU)

    exported = {
        item.name: b"".join([chunk async for chunk in item.chunks])
        async for item in handler.export(russian)
    }
    await handler.copy(russian, Home.EU)
    await handler.copy(russian, Home.EU)
    same = await handler.manifest(russian) == await handler.manifest(european)
    async with homes.transactions.begin(TenancyScope(Home.EU, person), read_only=True) as session:
        moved = set(await session.scalars(select(TaskPlacementRecord.task_id)))
        lines_moved = set(await session.scalars(select(TaskSubtaskRecord.task_id)))
    await handler.erase(russian)
    await handler.erase(russian)
    await handler.purge(european)
    async with homes.transactions.begin(TenancyScope(Home.RU, person, org)) as session:
        left = set(await session.scalars(select(TaskRecord.id)))
        comments_left = set(await session.scalars(select(TaskCommentRecord.task_id)))

    assert set(exported) == {
        "tasks.jsonl", "meeting_task_sets.jsonl", "boards.jsonl", "board_columns.jsonl",
        "task_placements.jsonl", "task_settings.jsonl", "task_subtasks.jsonl",
        "task_comments.jsonl", "task_attachments.jsonl",
    }  # fmt: skip
    assert str(own).encode() in exported["task_comments.jsonl"]
    assert str(shared).encode() not in exported["task_subtasks.jsonl"]
    assert str(own).encode() in exported["tasks.jsonl"]
    assert str(shared).encode() not in exported["tasks.jsonl"]
    assert str(shared).encode() in exported["task_placements.jsonl"]
    assert same
    assert moved == lines_moved == {own}
    assert left == comments_left == {shared}
    assert released.ids == [HELD, HELD]
    assert await handler.remains(russian) == ()
    assert await handler.remains(european) == ()
