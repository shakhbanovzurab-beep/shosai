"""Files' tables: the shareable `file` resource obeys the access rules; usage is never negative."""

import uuid

import psycopg
import pytest
import sqlalchemy as sa

from shosai.core.events.catalog import EventTypes
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.files.application.visibility import visible_files
from shosai.features.files.infrastructure.file_records import FILE_RESOURCE, StorageFileRecord
from shosai.features.workspaces.application.access_policy import WorkspaceAccessPolicy
from shosai.features.workspaces.contracts import Viewer
from shosai.features.workspaces.infrastructure.audit_log import WorkspaceAuditLog
from shosai.features.workspaces.module import WORKSPACES
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot
from tests.support.isolation import assert_isolated

# Обязательные колонки строки файла, общие для всего мира проверки.
FILE_COLUMNS = {
    "name": "Report.pdf",
    "content_type": "application/pdf",
    "size_bytes": 1024,
    "object_key": "u/probe/f/probe",
}


def policy() -> WorkspaceAccessPolicy:
    return WorkspaceAccessPolicy(
        EventOutbox(EventTypes(list(WORKSPACES.events))), WorkspaceAuditLog()
    )


@pytest.mark.isolation(resource="file")
@pytest.mark.parametrize("home", list(Home))
async def test_the_files_a_person_sees_obey_the_access_rules(
    homes: DatabaseAccess, run_slot: RunSlot, home: Home
) -> None:
    async def path(viewer: Viewer) -> set[uuid.UUID]:
        async with homes.transactions.begin(
            TenancyScope(home, viewer.user_id), read_only=True
        ) as session:
            return {
                row.id for row in (await session.scalars(visible_files(policy(), viewer))).all()
            }

    await assert_isolated(run_slot.claimed.connections[home], FILE_RESOURCE, path, FILE_COLUMNS)


async def test_a_hidden_file_is_seen_by_nobody_not_even_its_owner(homes: DatabaseAccess) -> None:
    owner = uuid.uuid4()
    shown, hidden = uuid.uuid4(), uuid.uuid4()
    scope = TenancyScope(Home.RU, owner)
    async with homes.transactions.begin(scope) as session:
        session.add_all(
            [
                StorageFileRecord(id=shown, user_id=owner, **FILE_COLUMNS),
                StorageFileRecord(
                    id=hidden, user_id=owner, deleted_at=sa.func.now(), **FILE_COLUMNS
                ),
            ]
        )
    async with homes.transactions.begin(scope, read_only=True) as session:
        seen = {
            row.id for row in (await session.scalars(visible_files(policy(), Viewer(owner)))).all()
        }

    assert seen == {shown}


@pytest.mark.parametrize(
    "statement",
    [
        "INSERT INTO storage_usage (user_id, used_bytes) VALUES (%s, -1)",
        "INSERT INTO storage_usage (user_id, reserved_bytes) VALUES (%s, -1)",
        "INSERT INTO storage_usage (user_id, reminders_sent) VALUES (%s, 1)",
        "INSERT INTO storage_files"
        " (id, user_id, org_id, name, content_type, size_bytes, object_key)"
        " VALUES (%s, gen_random_uuid(), gen_random_uuid(), 'a', 'b', 1, 'k')",
    ],
)
async def test_the_database_refuses_negative_usage_and_broken_rows(
    homes: DatabaseAccess, run_slot: RunSlot, statement: str
) -> None:
    connection = run_slot.claimed.connections[Home.EU]

    with pytest.raises(psycopg.errors.CheckViolation):
        await connection.execute(statement, (uuid.uuid4(),))
