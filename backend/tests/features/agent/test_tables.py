"""Agent's tables: a person's rows are theirs alone, and the database keeps the rules (§3.4)."""

import uuid
from datetime import UTC, datetime

import psycopg
import pytest
from sqlalchemy import select, text, update
from sqlalchemy.exc import DBAPIError

from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.agent.infrastructure.person_records import (
    AgentEvalCaseRecord,
    AgentFeedbackRecord,
    AgentSettingsRecord,
)
from shosai.features.agent.infrastructure.run_records import AgentActionRecord, AgentAuditRecord
from shosai.features.agent.infrastructure.thread_records import (
    AgentMessageRecord,
    AgentThreadRecord,
)
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot

NOW = datetime.now(UTC)
THREAD = (
    "INSERT INTO agent_threads (id, user_id, scope_kind, org_id, hub_id, title)"
    " VALUES (%s, %s, %s, %s, %s, %s)"
)


def thread(person: uuid.UUID, **fields: object) -> AgentThreadRecord:
    values: dict[str, object] = {"scope_kind": "personal", "title": "Бюджет"} | fields
    return AgentThreadRecord(id=uuid.uuid4(), user_id=person, **values)


async def test_a_person_never_reads_or_writes_anothers_rows(homes: DatabaseAccess) -> None:
    owner, other = uuid.uuid4(), uuid.uuid4()
    async with homes.transactions.begin(TenancyScope(Home.RU, owner)) as session:
        session.add(thread(owner))
        session.add(AgentSettingsRecord(user_id=owner, web_search=False))
    async with homes.transactions.begin(TenancyScope(Home.RU, other), read_only=True) as session:
        assert (await session.scalars(select(AgentThreadRecord.id))).all() == []
        assert (await session.scalars(select(AgentSettingsRecord.user_id))).all() == []

    with pytest.raises(DBAPIError, match="row-level security"):
        async with homes.transactions.begin(TenancyScope(Home.RU, other)) as session:
            session.add(thread(owner))


@pytest.mark.parametrize(
    ("scope_kind", "org", "hub", "title"),
    [
        ("workspace", None, None, "Бюджет"),
        ("personal", uuid.uuid4(), None, "Бюджет"),
        ("hub", None, None, "Бюджет"),
        ("personal", None, None, ""),
        ("personal", None, None, "я" * 121),
        ("team", None, None, "Бюджет"),
    ],
)
async def test_the_database_refuses_a_thread_breaking_its_rules(
    run_slot: RunSlot, scope_kind: str, org: uuid.UUID | None, hub: uuid.UUID | None, title: str
) -> None:
    connection = run_slot.claimed.connections[Home.EU]

    with pytest.raises(psycopg.errors.CheckViolation):
        await connection.execute(THREAD, (uuid.uuid4(), uuid.uuid4(), scope_kind, org, hub, title))


async def test_an_answer_has_a_status_and_a_tool_row_names_its_call(run_slot: RunSlot) -> None:
    connection = run_slot.claimed.connections[Home.RU]
    person, thread_id = uuid.uuid4(), uuid.uuid4()
    await connection.execute(THREAD, (thread_id, person, "personal", None, None, "Тред"))
    message = (
        "INSERT INTO agent_messages (id, created_at, thread_id, user_id, role, status,"
        " tool_call_id, tool_name) VALUES (%s, now(), %s, %s, %s, %s, %s, %s)"
    )

    await connection.execute(message, (uuid.uuid4(), thread_id, person, "user", None, None, None))
    for role, status, call, tool in (
        ("assistant", None, None, None),
        ("user", "done", None, None),
        ("tool", None, None, "notes.search"),
        ("user", None, "call-1", "notes.search"),
    ):
        with pytest.raises(psycopg.errors.CheckViolation):
            await connection.execute(
                message, (uuid.uuid4(), thread_id, person, role, status, call, tool)
            )


async def test_deleting_a_thread_takes_its_rows_and_frees_its_actions(
    homes: DatabaseAccess,
) -> None:
    person = uuid.uuid4()
    scope = TenancyScope(Home.RU, person)
    own = thread(person)
    answer, action = uuid.uuid4(), uuid.uuid4()
    async with homes.transactions.begin(scope) as session:
        session.add(own)
        await session.flush()
        session.add(
            AgentMessageRecord(
                id=answer, created_at=NOW, thread_id=own.id, user_id=person, role="assistant",
                status="done", text="Ответ",
            )
        )  # fmt: skip
        session.add(
            AgentFeedbackRecord(
                message_id=answer, user_id=person, thread_id=own.id, rating="useful"
            )
        )
        await session.flush()
        session.add(
            AgentEvalCaseRecord(
                id=uuid.uuid4(), user_id=person, message_id=answer, thread_id=own.id,
                rating="useful", language="ru", case={"question": "?"}, prompt_version="p1",
            )
        )  # fmt: skip
        session.add(action_record(action, person, own.id))
    async with homes.transactions.begin(scope) as session:
        await session.delete(await session.get(AgentThreadRecord, own.id))
    async with homes.transactions.begin(scope, read_only=True) as session:
        assert (await session.scalars(select(AgentMessageRecord.id))).all() == []
        assert (await session.scalars(select(AgentFeedbackRecord.message_id))).all() == []
        assert (await session.scalars(select(AgentEvalCaseRecord.id))).all() == []
        assert await session.scalar(
            select(AgentActionRecord.thread_id).where(AgentActionRecord.id == action)
        ) is None  # fmt: skip


def action_record(
    action: uuid.UUID, person: uuid.UUID, thread_id: uuid.UUID | None
) -> AgentActionRecord:
    return AgentActionRecord(
        id=action, user_id=person, thread_id=thread_id, origin="turn", nonce="n",
        items=[{"tool": "tasks.create"}], expires_at=NOW,
    )  # fmt: skip


async def test_an_action_has_items_and_is_resolved_exactly_when_over(
    homes: DatabaseAccess,
) -> None:
    person = uuid.uuid4()
    scope = TenancyScope(Home.EU, person)
    cases: tuple[dict[str, object], ...] = (
        {"items": []},
        {"status": "succeeded"},
        {"resolved_at": NOW},
    )
    for broken in cases:
        record = action_record(uuid.uuid4(), person, None)
        for name, value in broken.items():
            setattr(record, name, value)
        with pytest.raises(DBAPIError, match="check constraint"):
            async with homes.transactions.begin(scope) as session:
                session.add(record)


async def test_the_application_only_appends_to_the_audit(homes: DatabaseAccess) -> None:
    person = uuid.uuid4()
    scope = TenancyScope(Home.RU, person)
    event = uuid.uuid4()
    async with homes.transactions.begin(scope) as session:
        session.add(
            AgentAuditRecord(
                id=event, created_at=NOW, user_id=person, action_id=uuid.uuid4(), event="proposed"
            )
        )

    with pytest.raises(DBAPIError, match="permission denied"):
        async with homes.transactions.begin(scope) as session:
            await session.execute(
                update(AgentAuditRecord).where(AgentAuditRecord.id == event).values(code="x")
            )
    with pytest.raises(DBAPIError, match="permission denied"):
        async with homes.transactions.begin(scope) as session:
            await session.execute(text("DELETE FROM agent_audit"))
