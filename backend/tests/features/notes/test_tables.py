"""Notes' tables: the `meeting` resource obeys the access rules; the database keeps the rules."""

import uuid
from datetime import UTC, datetime, timedelta

import psycopg
import pytest
import sqlalchemy as sa

from shosai.core.events.catalog import EventTypes
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.notes.application.visibility import visible_meetings
from shosai.features.notes.infrastructure.meeting_records import MEETING_RESOURCE, MeetingRecord
from shosai.features.workspaces.application.access_policy import WorkspaceAccessPolicy
from shosai.features.workspaces.contracts import Viewer
from shosai.features.workspaces.infrastructure.audit_log import WorkspaceAuditLog
from shosai.features.workspaces.module import WORKSPACES
from tests.harness.connections import fetch_value
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot
from tests.support.isolation import assert_isolated

STARTED = datetime.now(UTC)
# Обязательные колонки встречи, общие для всего мира проверки.
MEETING_COLUMNS = {"title": "Созвон", "started_at": STARTED}
SHARED_MEETING = sa.text("SELECT session_id, org_id FROM meetings_shared_meeting(:token)")


def policy() -> WorkspaceAccessPolicy:
    return WorkspaceAccessPolicy(
        EventOutbox(EventTypes(list(WORKSPACES.events))), WorkspaceAuditLog()
    )


@pytest.mark.isolation(resource="meeting")
@pytest.mark.parametrize("home", list(Home))
async def test_the_meetings_a_person_sees_obey_the_access_rules(
    homes: DatabaseAccess, run_slot: RunSlot, home: Home
) -> None:
    async def path(viewer: Viewer) -> set[uuid.UUID]:
        async with homes.transactions.begin(
            TenancyScope(home, viewer.user_id), read_only=True
        ) as session:
            rows = (await session.scalars(visible_meetings(policy(), viewer))).all()
            return {row.id for row in rows}

    await assert_isolated(
        run_slot.claimed.connections[home], MEETING_RESOURCE, path, MEETING_COLUMNS
    )


async def test_a_deleted_meeting_is_seen_by_nobody_not_even_its_owner(
    homes: DatabaseAccess,
) -> None:
    owner, shown, hidden = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    scope = TenancyScope(Home.RU, owner)
    async with homes.transactions.begin(scope) as session:
        session.add_all(
            [
                MeetingRecord(id=shown, user_id=owner, **MEETING_COLUMNS),
                MeetingRecord(
                    id=hidden, user_id=owner, deleted_at=sa.func.now(), **MEETING_COLUMNS
                ),
            ]
        )
    async with homes.transactions.begin(scope, read_only=True) as session:
        seen = {
            row.id for row in (await session.scalars(visible_meetings(policy(), Viewer(owner))))
        }

    assert seen == {shown}


async def test_a_seq_is_unique_in_a_meeting_across_the_months_end(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    connection = run_slot.claimed.connections[Home.EU]
    month_end = await fetch_value(
        connection, "SELECT date_trunc('month', now()) + interval '1 month' - interval '1 minute'"
    )
    assert isinstance(month_end, datetime)
    meeting, owner = uuid.uuid4(), uuid.uuid4()
    await connection.execute(
        "INSERT INTO sessions (id, user_id, title, started_at) VALUES (%s, %s, 'Ночь', %s)",
        (meeting, owner, month_end),
    )
    line = (
        "INSERT INTO transcript_segments (session_id, seq, meeting_started_at, started_at,"
        " start_ms, duration_ms, text) VALUES (%s, 1, %s, %s, 0, 900, 'Да.')"
    )
    await connection.execute(line, (meeting, month_end, month_end))

    with pytest.raises(psycopg.errors.UniqueViolation):
        await connection.execute(line, (meeting, month_end, month_end + timedelta(minutes=2)))


@pytest.mark.parametrize("home", list(Home))
async def test_a_links_token_answers_only_its_meeting_and_company_past_row_security(
    homes: DatabaseAccess, run_slot: RunSlot, home: Home
) -> None:
    connection = run_slot.claimed.connections[home]
    meeting, owner, workspace = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    other = uuid.uuid4()
    for session_id, org in ((meeting, workspace), (other, None)):
        await connection.execute(
            "INSERT INTO sessions (id, user_id, org_id, access, title, started_at)"
            " VALUES (%s, %s, %s, %s, 'Совет', now())",
            (session_id, owner, org, None if org is None else "organization"),
        )
    await connection.execute(
        "INSERT INTO meeting_result_shares (session_id, user_id, org_id, token)"
        " VALUES (%s, %s, %s, 'tok_en-1'), (%s, %s, NULL, 'other-token')",
        (meeting, owner, workspace, other, owner),
    )

    async with homes.transactions.begin(TenancyScope(home), read_only=True) as session:
        found = (await session.execute(SHARED_MEETING, {"token": "tok_en-1"})).all()
        unknown = (await session.execute(SHARED_MEETING, {"token": "nope"})).all()
        visible = await session.scalar(sa.select(sa.func.count()).select_from(MeetingRecord))

    assert [tuple(row) for row in found] == [(meeting, workspace)]
    assert unknown == []
    assert visible == 1


@pytest.mark.parametrize(
    "statement",
    [
        "INSERT INTO sessions (id, user_id, title, started_at, ended_at)"
        " VALUES (%s, gen_random_uuid(), 't', now(), now())",
        "INSERT INTO sessions (id, user_id, title, started_at, status, ended_at)"
        " VALUES (%s, gen_random_uuid(), 't', now(), 'completed', now() - interval '1 hour')",
        "INSERT INTO sessions (id, user_id, title, started_at)"
        " VALUES (%s, gen_random_uuid(), '', now())",
        "INSERT INTO sessions (id, user_id, org_id, title, started_at)"
        " VALUES (%s, gen_random_uuid(), gen_random_uuid(), 't', now())",
        "INSERT INTO meeting_folders (id, user_id, name, color)"
        " VALUES (%s, gen_random_uuid(), 'f', 'pink')",
        "INSERT INTO meeting_templates (id, user_id, name, icon, sections)"
        " VALUES (%s, gen_random_uuid(), 'n', 'rocket', '{}')",
    ],
)
async def test_the_database_refuses_broken_rows(
    homes: DatabaseAccess, run_slot: RunSlot, statement: str
) -> None:
    connection = run_slot.claimed.connections[Home.RU]

    with pytest.raises(psycopg.errors.CheckViolation):
        await connection.execute(statement, (uuid.uuid4(),))
