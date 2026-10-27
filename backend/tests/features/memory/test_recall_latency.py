"""Exact recall over one person's facts within ADR 0033's 20 ms (memory step 2, MM-D6).

The home holds one person's 5 000 current facts — ADR 0030's limit — interleaved with 24 000
facts of 400 others, the way rows land when everyone talks to Leo at once, and 1 000 ended
facts of the person. The nearest 40 of the person's current facts by cosine, read through the
b-tree on the person, take at most 20 ms — the statement itself, as ADR 0033 counts it; the
transaction around it is every read's and is counted in a turn's budget (Leo §12). On a shared
test server the median is held here, where it is stable; ADR 0033's p95 is watched in production
by `shosai_memory_recall_seconds`. No HNSW is needed.
"""

import statistics
import time
import uuid
from typing import Final

from sqlalchemy import select

from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.memory.infrastructure.records import (
    EMBEDDING_DIMENSIONS,
    MemoryFactRecord,
)
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot

OBJECTIVE: Final = 0.020
SAMPLES: Final = 40
WARM_UP: Final = 3
OWN: Final = 5_000
ENDED: Final = 1_000
MODEL: Final = "baai/bge-m3"
# Факты вперемешку: каждый пятый — человека, остальные — четырёхсот других; векторы случайные.
SEED: Final = """
INSERT INTO memory_facts (id, user_id, kind, statement, source_kind, status, ended_reason,
                          ended_at, embedding, embedding_model)
SELECT gen_random_uuid(),
       CASE WHEN g %% 5 = 0 THEN %(person)s::uuid ELSE md5('u' || (g %% 400))::uuid END,
       'fact', 'Fact number ' || g, 'user_statement',
       CASE WHEN g %% 5 = 0 AND g > %(total)s - %(ended)s * 5 THEN 'forgotten' ELSE 'active' END,
       CASE WHEN g %% 5 = 0 AND g > %(total)s - %(ended)s * 5 THEN 'forgot' END,
       CASE WHEN g %% 5 = 0 AND g > %(total)s - %(ended)s * 5 THEN now() END,
       (SELECT array_agg(random()::real - 0.5)::halfvec
        FROM generate_series(1, %(dims)s) WHERE g > 0),
       %(model)s
FROM generate_series(1, %(total)s) AS g
"""


async def test_the_nearest_forty_of_five_thousand_facts_take_under_twenty_ms(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    person = uuid.uuid4()
    total = (OWN + ENDED) * 5
    connection = run_slot.claimed.connections[Home.RU]
    params = {
        "person": person, "total": total, "ended": ENDED, "dims": EMBEDDING_DIMENSIONS,
        "model": MODEL,
    }  # fmt: skip
    async with connection.transaction():
        await connection.execute(SEED, params)
    await connection.execute("ANALYZE memory_facts")
    query = [0.01 * (index % 7) - 0.03 for index in range(EMBEDDING_DIMENSIONS)]
    distance = MemoryFactRecord.embedding.cosine_distance(query)
    statement = (
        select(MemoryFactRecord.id, distance)
        .where(
            MemoryFactRecord.user_id == person,
            MemoryFactRecord.status == "active",
            MemoryFactRecord.valid_to.is_(None),
            MemoryFactRecord.embedding_model == MODEL,
        )
        .order_by(distance)
        .limit(40)
    )
    timings: list[float] = []
    found = 0
    scope = TenancyScope(Home.RU, person)
    for sample in range(SAMPLES + WARM_UP):
        async with homes.transactions.begin(scope, read_only=True) as session:
            started = time.perf_counter()
            found = len((await session.execute(statement)).all())
            took = time.perf_counter() - started
        if sample >= WARM_UP:
            timings.append(took)
    median = statistics.median(timings)
    assert found == 40
    assert median <= OBJECTIVE, f"median {median * 1000:.1f} ms"
