"""Recall at the design point's peak (memory step 11, plan §1.3).

The Russian home holds 100 people with 250 current facts each and one with 5 000 — ADR 0030's
limit — every vector close to the question's, so each recall reads its nearest 40, packs 12
and gives them. Recalls arrive at 29 a second for 10 seconds, the whole platform's peak at
100 000 DAU, in one process and one database pool, where production spreads them over the
agent workers. The embedding double answers after 100 ms. At most 2 % of recalls are late
(350 ms) — a late one gives the turn nothing and the turn goes on — and the platform's own
part, the time beyond the embedding, stays within the bench's bound at p95; the numbers are
logged for the plan (`--log-cli-level=INFO`).
"""

import asyncio
import logging
import statistics
import time
import uuid
from datetime import timedelta
from typing import Final

from shosai.core.config.roles import ProcessRole
from shosai.core.db.engines import DATABASE_PROFILES
from shosai.core.kernel.homes import Home
from shosai.features.memory.domain.packing import RECALL_FACTS
from shosai.features.memory.infrastructure.records import EMBEDDING_DIMENSIONS
from tests.features.memory.recall_bench import MODEL, RecallBench, axis
from tests.harness.run_slot import RunSlot

log = logging.getLogger(__name__)

PEOPLE: Final = 100
EACH: Final = 250
LARGEST: Final = 5_000
RATE: Final = 29
SECONDS: Final = 10
EMBEDDING: Final = timedelta(milliseconds=100)
# Пул прогрет до своего размера, как у воркера в работе: замер — не открытие соединений.
POOL: Final = DATABASE_PROFILES[ProcessRole.API].pool_size
# Опоздавшее вспоминание ход не ждёт. Одна пауза общего хоста (≈ 0,4 с при load average 6–9,
# замер 2026-10-28) накрывает четыре вспоминания в полёте — 1,4 %; допуск — одна такая пауза.
# Регрессию вроде загрузки векторов со строкой ловит граница p95.
LATE_SHARE: Final = 0.02
# Предел стенда: все вспоминания пика в одном процессе и одном пуле, на хосте рядом со staging.
PLATFORM_P95_MS: Final = 150
# Векторы фактов близки к вопросу: каждое вспоминание читает свои 40 и отдаёт 12.
SEED: Final = """
INSERT INTO memory_facts (id, user_id, kind, statement, source_kind, status, confirmed,
                          embedding, embedding_model)
SELECT gen_random_uuid(), person, 'fact', 'Fact number ' || g || ' of the person', 'user_statement',
       'active', true,
       (SELECT (array[1::real] || array_agg((random()::real - 0.5) * 0.02))::halfvec
        FROM generate_series(2, %(dims)s) WHERE g > 0),
       %(model)s
FROM unnest(%(people)s::uuid[], %(counts)s::int[]) AS p(person, total),
     LATERAL generate_series(1, total) AS g
"""


async def test_recall_at_the_peak_keeps_its_deadline(
    recall_bench: RecallBench, run_slot: RunSlot
) -> None:
    people = [uuid.uuid4() for _ in range(PEOPLE + 1)]
    counts = [EACH] * PEOPLE + [LARGEST]
    connection = run_slot.claimed.connections[Home.RU]
    params = {"people": people, "counts": counts, "dims": EMBEDDING_DIMENSIONS, "model": MODEL}
    async with connection.transaction():
        await connection.execute(SEED, params)
    await connection.execute("ANALYZE memory_facts")
    recall_bench.model.known["What do I like?"] = axis(1)
    recall_bench.model.delay = EMBEDDING

    async def timed(person: uuid.UUID) -> tuple[float, int]:
        started = time.perf_counter()
        facts = await recall_bench.recall.recall(recall_bench.ask(person, "What do I like?"))
        return time.perf_counter() - started, len(facts)

    # Пул наполняется до замера: вызовы разом по числу соединений, среди них человек с 5 000.
    await asyncio.gather(*(timed(person) for person in people[-POOL:]))
    calls = []
    for index in range(RATE * SECONDS):
        calls.append(asyncio.create_task(timed(people[index % len(people)])))
        await asyncio.sleep(1 / RATE)
    results = await asyncio.gather(*calls)

    platform = sorted(max(took - EMBEDDING.total_seconds(), 0) * 1000 for took, _ in results)
    p50, p95 = statistics.median(platform), platform[int(len(platform) * 0.95)]
    late = sum(found != RECALL_FACTS for _, found in results)
    log.info(
        "вспоминание на пике: %s вызовов, опоздали %s, время платформы p50 %.0f мс, p95 %.0f мс, "
        "max %.0f мс",
        len(results), late, p50, p95, platform[-1],
    )  # fmt: skip
    assert late <= len(results) * LATE_SHARE, f"опоздали {late}"
    assert p95 <= PLATFORM_P95_MS, f"p50 {p50:.0f} ms, p95 {p95:.0f} ms"
