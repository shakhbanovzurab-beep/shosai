"""Memory's tables: a person's own rows only, the database keeping a fact's rules, vectors
stored inline and compared in the database (memory plan §3.6)."""

import uuid
from collections.abc import Mapping
from datetime import UTC, datetime

import pytest
from sqlalchemy import insert, select, text
from sqlalchemy.exc import DBAPIError

from shosai.core.config.roles import ProcessRole
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.memory.infrastructure.records import (
    EMBEDDING_DIMENSIONS,
    MemoryFactRecord,
    MemorySettingsRecord,
    MemorySummaryRecord,
)
from tests.harness.database_access import (
    DatabaseAccess,
    ProcessShape,
    open_database_access,
    slot_urls,
)
from tests.harness.run_slot import RunSlot

NOW = datetime.now(UTC)
MODEL = "baai/bge-m3"


def vector(hot: int) -> list[float]:
    """A unit vector along one axis."""
    return [1.0 if index == hot else 0.0 for index in range(EMBEDDING_DIMENSIONS)]


def row(person: uuid.UUID, **fields: object) -> dict[str, object]:
    """A current fact's columns, the person's own words by default."""
    return {
        "id": uuid.uuid4(), "user_id": person, "kind": "fact",
        "statement": "Leads product at Lumen", "source_kind": "user_statement",
        "status": "active",
    } | fields  # fmt: skip


async def add(homes: DatabaseAccess, person: uuid.UUID, *rows: Mapping[str, object]) -> None:
    """Insert facts as the person in the Russian home."""
    async with homes.transactions.begin(TenancyScope(Home.RU, person)) as session:
        await session.execute(insert(MemoryFactRecord), [dict(item) for item in rows])


async def test_a_person_reads_and_writes_only_their_own_rows(homes: DatabaseAccess) -> None:
    person, other = uuid.uuid4(), uuid.uuid4()
    await add(homes, person, row(person))
    async with homes.transactions.begin(TenancyScope(Home.RU, person)) as session:
        session.add(MemorySettingsRecord(user_id=person, enabled=False))
        session.add(MemorySummaryRecord(user_id=person, language="ru"))
    async with homes.transactions.begin(TenancyScope(Home.RU, other), read_only=True) as session:
        seen = [
            (await session.scalars(select(model.user_id))).all()
            for model in (MemoryFactRecord, MemorySettingsRecord, MemorySummaryRecord)
        ]
    assert seen == [[], [], []]
    with pytest.raises(DBAPIError, match="row-level security"):
        await add(homes, other, row(person))


@pytest.mark.parametrize(
    ("fields", "rule"),
    [
        ({"kind": "episode"}, "kind_known"),
        ({"source_kind": "mail"}, "source_known"),
        ({"status": "deleted"}, "status_known"),
        ({"statement": ""}, "statement_length"),
        ({"statement": "x" * 501}, "statement_length"),
        ({"confidence": 1.5}, "confidence_range"),
        ({"status": "candidate", "pinned": True}, "pinned_when_active"),
        ({"status": "forgotten"}, "ended_when_forgotten"),
        ({"ended_reason": "forgot", "ended_at": NOW}, "ended_when_forgotten"),
        ({"superseded_by": uuid.uuid4()}, "superseded_closed"),
        ({"embedding": vector(0)}, "embedding_with_model"),
        ({"source_taint": "suspicious"}, "source_taint_known"),
    ],
)
async def test_the_database_keeps_a_facts_rules(
    homes: DatabaseAccess, fields: dict[str, object], rule: str
) -> None:
    person = uuid.uuid4()
    with pytest.raises(DBAPIError, match=rule):
        await add(homes, person, row(person, **fields))


async def test_vectors_stay_inline_and_are_compared_in_the_database(
    homes: DatabaseAccess,
) -> None:
    person = uuid.uuid4()
    near, far = (
        row(person, embedding=vector(1), embedding_model=MODEL),
        row(person, statement="Lives in Berlin", embedding=vector(2), embedding_model=MODEL),
    )
    await add(homes, person, near, far)
    query = vector(1)
    async with homes.transactions.begin(TenancyScope(Home.RU, person), read_only=True) as session:
        distance = MemoryFactRecord.embedding.cosine_distance(query)
        ranked = (
            await session.execute(select(MemoryFactRecord.id, distance).order_by(distance).limit(2))
        ).all()
        stored = await session.scalar(select(MemoryFactRecord.embedding).limit(1))
        storage = await session.scalar(
            text(
                "SELECT attstorage FROM pg_attribute"
                " WHERE attrelid = 'memory_facts'::regclass AND attname = 'embedding'"
            )
        )
    assert [item[0] for item in ranked] == [near["id"], far["id"]]
    assert ranked[0][1] == pytest.approx(0.0)
    assert ranked[1][1] == pytest.approx(1.0)
    assert stored is not None
    assert len(stored) == EMBEDDING_DIMENSIONS
    assert storage == "p"


async def test_the_sweep_role_reads_facts_and_summaries(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    person = uuid.uuid4()
    await add(homes, person, row(person, status="candidate"))
    async with homes.transactions.begin(TenancyScope(Home.RU, person)) as session:
        session.add(MemorySummaryRecord(user_id=person, language="ru", stale=True))
    shape = ProcessShape(role=ProcessRole.WORKERS)
    async with open_database_access(slot_urls(run_slot), shape) as workers:
        await workers.gate.verify_at_start()
        scope = TenancyScope(Home.RU)
        async with workers.transactions.begin(scope, read_only=True, sweep=True) as session:
            facts = (
                await session.scalars(
                    select(MemoryFactRecord.id).where(MemoryFactRecord.user_id == person)
                )
            ).all()
            stale = await session.scalar(
                select(MemorySummaryRecord.stale).where(MemorySummaryRecord.user_id == person)
            )
    assert len(facts) == 1
    assert stale is True
