"""The embedding pass: every waiting fact gets the current model's vector, as its person allows
(memory step 4)."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update

from shosai.core.ai.errors import AiFailure
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.memory.infrastructure.records import MemoryFactRecord
from tests.features.memory.recall_bench import MODEL, RecallBench, axis


async def vectors(bench: RecallBench, person: uuid.UUID) -> dict[str, str | None]:
    """Each statement's model, or None without a vector."""
    scope = TenancyScope(Home.RU, person)
    async with bench.homes.transactions.begin(scope, read_only=True) as session:
        rows = await session.execute(
            select(MemoryFactRecord.statement, MemoryFactRecord.embedding_model)
        )
        return {row.statement: row.embedding_model for row in rows}


async def test_waiting_facts_get_vectors_and_only_as_their_person_allows(
    recall_bench: RecallBench,
) -> None:
    person, refusing = uuid.uuid4(), uuid.uuid4()
    recall_bench.consents.given.add(person)
    await recall_bench.add(
        person,
        [
            {"statement": "Fresh"},
            {"statement": "Waiting", "status": "candidate"},
            {"statement": "Old model", "embedding": axis(1), "embedding_model": "other/model"},
            {"statement": "Done", "embedding": axis(1), "embedding_model": MODEL},
            {"statement": "Gone", "status": "forgotten", "ended_reason": "forgot",
             "ended_at": datetime.now(UTC)},
        ],
    )  # fmt: skip
    await recall_bench.add(refusing, [{"statement": "Not allowed"}])

    for _ in range(3):
        await recall_bench.embedding.run(Home.RU)

    assert await vectors(recall_bench, person) == {
        "Fresh": MODEL, "Waiting": MODEL, "Old model": MODEL, "Done": MODEL, "Gone": None,
    }  # fmt: skip
    assert await vectors(recall_bench, refusing) == {"Not allowed": None}
    embedded = [texts for _, texts, later in recall_bench.model.calls if not later]
    assert sorted(text for texts in embedded for text in texts) == [
        "title: none | text: Fresh",
        "title: none | text: Old model",
        "title: none | text: Waiting",
    ]


async def test_a_statement_changed_meanwhile_keeps_what_the_person_did(
    recall_bench: RecallBench,
) -> None:
    person = uuid.uuid4()
    recall_bench.consents.given.add(person)
    (fact,) = await recall_bench.add(person, [{"statement": "Before"}])
    scope = TenancyScope(Home.RU, person)

    async def edit_meanwhile() -> None:
        async with recall_bench.homes.transactions.begin(scope) as session:
            await session.execute(
                update(MemoryFactRecord)
                .where(MemoryFactRecord.id == fact)
                .values(statement="After")
            )

    recall_bench.model.meanwhile = edit_meanwhile
    await recall_bench.embedding.run(Home.RU)

    assert await vectors(recall_bench, person) == {"After": None}


async def test_a_failed_call_leaves_the_facts_waiting(recall_bench: RecallBench) -> None:
    person = uuid.uuid4()
    recall_bench.consents.given.add(person)
    await recall_bench.add(person, [{"statement": "Waits"}])
    recall_bench.model.failure = AiFailure.PROVIDER_ERROR

    await recall_bench.embedding.run(Home.RU)

    assert await vectors(recall_bench, person) == {"Waits": None}
