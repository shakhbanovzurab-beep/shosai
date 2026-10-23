"""Agent's part of a person's export, transfer and erasure (ADR 0045 point 7)."""

import uuid
from datetime import UTC, datetime

from redis.asyncio import Redis
from sqlalchemy import select

from shosai.core.account_data.handlers import AccountRef
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.agent.application.account_data import AgentAccountData
from shosai.features.agent.infrastructure.person_records import (
    AgentEvalCaseRecord,
    AgentFeedbackRecord,
    AgentSettingsRecord,
    AgentSkillRecord,
)
from shosai.features.agent.infrastructure.run_keys import lease_key, log_key
from shosai.features.agent.infrastructure.run_records import (
    AgentActionRecord,
    AgentAuditRecord,
    AgentRunRecord,
)
from shosai.features.agent.infrastructure.thread_records import (
    AgentMessageRecord,
    AgentThreadRecord,
    AgentToolResultRecord,
)
from tests.harness.database_access import DatabaseAccess

NOW = datetime.now(UTC)


async def seed(homes: DatabaseAccess, person: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    """A thread with a question and a rated answer, a tool result, a run, an action, settings
    and a skill."""
    thread, run = uuid.uuid4(), uuid.uuid4()
    answer = uuid.uuid4()
    async with homes.transactions.begin(TenancyScope(Home.RU, person)) as session:
        session.add(AgentThreadRecord(id=thread, user_id=person, scope_kind="personal", title="Т"))
        session.add(AgentSettingsRecord(user_id=person, response_length="concise"))
        session.add(
            AgentSkillRecord(
                id=uuid.uuid4(), user_id=person, source="github", repo="acme/skills",
                skill_path="pdf", ref="abc1234", slug="pdf", body="Use the PDF tools.",
            )
        )  # fmt: skip
        await session.flush()
        for message, role, status in ((uuid.uuid4(), "user", None), (answer, "assistant", "done")):
            session.add(
                AgentMessageRecord(
                    id=message, created_at=NOW, thread_id=thread, user_id=person, run_id=run,
                    role=role, status=status, text=f"{role} words",
                )
            )  # fmt: skip
        session.add(
            AgentToolResultRecord(
                id=uuid.uuid4(), created_at=NOW, user_id=person, run_id=run,
                tool_name="notes.search", payload={"meetings": []},
            )
        )  # fmt: skip
        session.add(
            AgentRunRecord(
                id=run, started_at=NOW, thread_id=thread, user_id=person, channel="web",
                status="completed", ended_at=NOW,
            )
        )  # fmt: skip
        session.add(
            AgentActionRecord(
                id=uuid.uuid4(), user_id=person, thread_id=thread, origin="turn", nonce="n",
                items=[{"tool": "tasks.create"}], expires_at=NOW,
            )
        )  # fmt: skip
        session.add(
            AgentAuditRecord(
                id=uuid.uuid4(), created_at=NOW, user_id=person, action_id=uuid.uuid4(),
                event="proposed",
            )
        )  # fmt: skip
        await session.flush()
        session.add(
            AgentFeedbackRecord(
                message_id=answer, user_id=person, thread_id=thread, rating="useful", shared=True
            )
        )
        await session.flush()
        session.add(
            AgentEvalCaseRecord(
                id=uuid.uuid4(), user_id=person, message_id=answer, thread_id=thread,
                rating="useful", language="ru", case={"answer": "assistant words"},
                prompt_version="p1",
            )
        )  # fmt: skip
    return thread, run


async def test_export_transfer_and_erasure_cover_every_row_and_live_key(
    homes: DatabaseAccess, valkey: Redis
) -> None:
    person = uuid.uuid4()
    thread, run = await seed(homes, person)
    await valkey.set(log_key(run), "events")
    await valkey.set(lease_key(thread), "run")
    handler = AgentAccountData(homes.transactions, valkey)
    russian, european = AccountRef(person, Home.RU), AccountRef(person, Home.EU)

    exported = {
        item.name: b"".join([chunk async for chunk in item.chunks])
        async for item in handler.export(russian)
    }
    await handler.copy(russian, Home.EU)
    await handler.copy(russian, Home.EU)
    same = await handler.manifest(russian) == await handler.manifest(european)
    async with homes.transactions.begin(TenancyScope(Home.EU, person), read_only=True) as session:
        moved_messages = len((await session.scalars(select(AgentMessageRecord.id))).all())
        moved_actions = (await session.scalars(select(AgentActionRecord.id))).all()
    await handler.erase(russian)
    await handler.erase(russian)
    await handler.purge(european)
    async with homes.transactions.begin(TenancyScope(Home.RU, person), read_only=True) as session:
        runs_left = (await session.scalars(select(AgentRunRecord.id))).all()

    assert set(exported) == {
        "agent_threads.jsonl", "agent_messages.jsonl", "agent_tool_results.jsonl",
        "agent_actions.jsonl", "agent_settings.jsonl", "agent_skills.jsonl",
        "agent_feedback.jsonl", "agent_eval_cases.jsonl",
    }  # fmt: skip
    assert b"assistant words" in exported["agent_messages.jsonl"]
    assert same
    assert moved_messages == 2
    assert moved_actions == []
    # Прогоны — числа и коды: истекают сами, со стиранием не уходят.
    assert runs_left == [run]
    assert await valkey.exists(log_key(run), lease_key(thread)) == 0
    assert await handler.remains(russian) == ()
    assert await handler.remains(european) == ()
