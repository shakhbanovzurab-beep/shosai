"""Memory's part of a person's export, transfer and erasure (ADR 0045 point 7): facts, the
switch, the summary and the traces of refusals, never a vector in the export."""

import json
import uuid
from datetime import UTC, datetime

from redis.asyncio import Redis
from sqlalchemy import insert, select

from shosai.core.account_data.handlers import AccountRef
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.memory.application.account_data import MemoryAccountData
from shosai.features.memory.infrastructure.presence import has_memories_key
from shosai.features.memory.infrastructure.records import (
    EMBEDDING_DIMENSIONS,
    MemoryFactRecord,
    MemoryRefusalRecord,
    MemorySettingsRecord,
    MemorySummaryRecord,
)
from tests.harness.database_access import DatabaseAccess

VECTOR = [0.5] * EMBEDDING_DIMENSIONS


async def seed(homes: DatabaseAccess, person: uuid.UUID) -> None:
    """A current fact with its vector, a candidate, a refusal's trace, the switch and the
    summary."""
    async with homes.transactions.begin(TenancyScope(Home.RU, person)) as session:
        await session.execute(
            insert(MemoryFactRecord),
            [
                {
                    "id": uuid.uuid4(), "user_id": person, "kind": "preference",
                    "statement": "Prefers short answers", "source_kind": "user_statement",
                    "status": "active", "confirmed": True, "embedding": VECTOR,
                    "embedding_model": "baai/bge-m3",
                },
                {
                    "id": uuid.uuid4(), "user_id": person, "kind": "relationship",
                    "statement": "Mara leads design", "source_kind": "meeting",
                    "status": "candidate", "source_taint": "external",
                },
            ],
        )  # fmt: skip
        await session.execute(
            insert(MemoryRefusalRecord),
            [{"id": uuid.uuid4(), "user_id": person, "embedding": VECTOR,
              "embedding_model": "baai/bge-m3", "refused_at": datetime.now(UTC)}],
        )  # fmt: skip
        session.add(MemorySettingsRecord(user_id=person, enabled=False))
        session.add(
            MemorySummaryRecord(
                user_id=person, language="en", sections=[{"title": "Work", "body": "Leads."}]
            )
        )


async def test_export_transfer_and_erasure_cover_every_row_and_the_bit(
    homes: DatabaseAccess, valkey: Redis
) -> None:
    person = uuid.uuid4()
    await seed(homes, person)
    await valkey.set(has_memories_key(person), "1")
    handler = MemoryAccountData(homes.transactions, valkey)
    russian, european = AccountRef(person, Home.RU), AccountRef(person, Home.EU)

    exported = {
        item.name: b"".join([chunk async for chunk in item.chunks])
        async for item in handler.export(russian)
    }
    await handler.copy(russian, Home.EU)
    await handler.copy(russian, Home.EU)
    same = await handler.manifest(russian) == await handler.manifest(european)
    async with homes.transactions.begin(TenancyScope(Home.EU, person), read_only=True) as session:
        moved = (await session.scalars(select(MemoryFactRecord.embedding))).all()
        traced = (await session.scalars(select(MemoryRefusalRecord.embedding))).all()
    await handler.erase(russian)
    await handler.erase(russian)
    await handler.purge(european)

    assert set(exported) == {
        "memory_facts.jsonl",
        "memory_settings.jsonl",
        "memory_summaries.jsonl",
        "memory_refusals.jsonl",
    }
    (trace,) = [json.loads(line) for line in exported["memory_refusals.jsonl"].splitlines()]
    assert set(trace) == {"id", "user_id", "refused_at"}
    facts = [json.loads(line) for line in exported["memory_facts.jsonl"].splitlines()]
    assert {fact["statement"] for fact in facts} == {"Prefers short answers", "Mara leads design"}
    assert all("embedding" not in fact and "embedding_model" not in fact for fact in facts)
    assert same
    assert sorted(vector is None for vector in moved) == [False, True]
    assert len(traced) == 1
    assert await valkey.exists(has_memories_key(person)) == 0
    assert await handler.remains(russian) == ()
    assert await handler.remains(european) == ()
