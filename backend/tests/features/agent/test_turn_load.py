"""One agent worker at its capacity: 48 Leo turns at once on a seeded home (agent step 17).

The EU home holds 200 threads of 100 messages each; 48 of them belong to the people who ask,
so every turn reads a full window of history. The 48 ask within 4 s — three times the peak
rate one worker gets at the design point (Leo §12: 29 turns/s over 8 workers at 100 K DAU) —
and the turns go through the real `agent` queue on the slot's Valkey to one consumer with the
queue's production profile (48 at once) and the production pace of writing text (100 ms). The
model double searches a tool, then streams about 800 tokens in 80 pieces over 8 s, as a real
answer does, so all 48 run at once at the peak. Every turn is answered and a 49th, asked then,
is refused with `agent_busy`; a turn writes 2 transactions in the API and 2 in the worker (the
model double skips the provider port, whose cost row adds one per model call); its log in
Valkey stays under 16 KB.

Time is held to the bench's bounds, which catch a regression like the one this step removed
(the API's log reader named every followed log on every read: 2-4 s of the platform's time),
not to the objective (95 % under 0.5 s for EU turns, §16.3): here the API's streams and the
worker's runs share one event loop and one database pool, twice a production process's work,
on a host shared with staging. The objective was measured in production's shape — the API and
the agent worker as their own processes, the model a double over HTTP — and is watched in
production by its alerts (agent plan, step 17). The numbers are logged for the plan
(`--log-cli-level=INFO`).
"""

import asyncio
import logging
import statistics
import time
import uuid
from dataclasses import dataclass, replace
from datetime import timedelta
from decimal import Decimal
from typing import Final

import httpx
import pytest
from opentelemetry.sdk.trace import TracerProvider
from prometheus_client import CollectorRegistry
from psycopg.rows import DictRow
from sqlalchemy import event

from shosai.core.ai.requests import ChatRequest, Role
from shosai.core.ai.results import ChatDelta, Usage
from shosai.core.tasks.declaration import TaskHandler
from shosai.core.tasks.queues import QUEUE_PROFILES, TaskQueue
from shosai.core.tasks.system import StreamOptions, TaskSystem, build_task_system
from shosai.features.agent.application.model_stream import DEFAULT_PACE
from shosai.features.agent.application.run_engine import RunEngine
from shosai.features.agent.application.turn_task import RUN_TURN
from shosai.features.agent.domain.runs import STREAM_STALL
from shosai.features.agent.infrastructure.run_keys import FLEET_RUNS, log_key
from tests.core.tasks.workbench import eventually, running
from tests.features.agent.tool_doubles import MODEL, calling
from tests.features.agent.turn_bench import HOME, TurnBench
from tests.harness.connections import Connection, fetch_rows

log = logging.getLogger(__name__)

CAPACITY: Final = QUEUE_PROFILES[TaskQueue.AGENT].concurrency
THREADS: Final = 200
PER_THREAD: Final = 100
PIECES: Final = 80
PIECE: Final = "Бюджет поездки сократили на 20 %, релиз — в пятницу. "
PAUSE: Final = 0.1
ARRIVALS: Final = 4.0
# Пределы стенда, где API и воркер делят один цикл событий (см. описание модуля).
OVERHEAD_P50_MS: Final = 500
OVERHEAD_P95_MS: Final = 1_500
PICKUP: Final = "shosai_agent_queue_pickup_seconds"
PICKUP_SECONDS: Final = "1.0"
LOG_BYTES: Final = 16 * 1024
# Две транзакции API (проверка до допуска и запись вопроса) и две воркера (контекст и конец).
TRANSACTIONS_PER_TURN: Final = 4
SEED: Final = """
INSERT INTO agent_threads (id, user_id, scope_kind, title, last_activity_at)
SELECT md5('load-thread' || g)::uuid,
       CASE WHEN g <= cardinality(%(people)s::uuid[]) THEN (%(people)s::uuid[])[g]
            ELSE md5('load-stranger' || g)::uuid END,
       'personal', 'Тред ' || g, now()
FROM generate_series(1, %(threads)s) AS g;
INSERT INTO agent_messages (id, created_at, thread_id, user_id, role, status, text, tokens)
SELECT gen_random_uuid(), now() - m * interval '1 second', t.id, t.user_id,
       CASE WHEN m %% 2 = 0 THEN 'user' ELSE 'assistant' END,
       CASE WHEN m %% 2 = 0 THEN NULL ELSE 'done' END,
       repeat('Обсуждали бюджет поездки и сроки релиза. ', 6), 60
FROM agent_threads AS t CROSS JOIN generate_series(1, %(per_thread)s) AS m
WHERE t.id IN (SELECT md5('load-thread' || g)::uuid FROM generate_series(1, %(threads)s) AS g)
"""


@pytest.fixture
def stream_silence() -> timedelta:
    """Production's silence: under load a stream waits on its log, not on the database."""
    return STREAM_STALL


def answering(request: ChatRequest) -> list[ChatDelta]:
    """A search first, then a long answer from what it found."""
    if not any(message.role is Role.TOOL for message in request.messages):
        return calling(("notes__search", '{"query": "budget"}'))
    usage = Usage(input_tokens=11_000, output_tokens=800, reported_cost_usd=Decimal("0.004"))
    end = ChatDelta(finish_reason="stop", usage=usage, model=MODEL)
    return [*(ChatDelta(text=PIECE) for _ in range(PIECES)), end]


async def seed(connection: Connection, people: list[uuid.UUID]) -> list[str]:
    """The seeded home; the threads of the people who ask, in their order."""
    params = {"people": people, "threads": THREADS, "per_thread": PER_THREAD}
    async with connection.transaction():
        for statement in SEED.split(";"):
            await connection.execute(statement, params)
        await connection.execute("ANALYZE agent_threads, agent_messages")
    rows = await fetch_rows(
        connection, "SELECT id, user_id FROM agent_threads WHERE user_id = ANY(%s)", (people,)
    )
    by_person = {row["user_id"]: str(row["id"]) for row in rows}
    return [by_person[person] for person in people]


def counts(registry: CollectorRegistry, name: str) -> dict[str, float]:
    """A histogram's cumulative counts by bound, `+Inf` for all of them."""
    return {
        sample.labels["le"]: sample.value
        for metric in registry.collect()
        if metric.name == name
        for sample in metric.samples
        if sample.name.endswith("_bucket")
    }


def share_within(before: dict[str, float], after: dict[str, float], bound: str) -> float:
    """The share of the observations between two readings at or under one of the bounds."""
    total = after["+Inf"] - before.get("+Inf", 0.0)
    return (after[bound] - before.get(bound, 0.0)) / total if total else 0.0


@dataclass(frozen=True, slots=True)
class Load:
    """What the 48 turns gave: their answers, the 49th's refusal and what they cost."""

    answers: list[httpx.Response]
    refused: httpx.Response
    transactions: int
    cpu_seconds: float
    pickup_before: dict[str, float]


def agent_queue(bench: TurnBench) -> TaskSystem:
    """The real `agent` queue over the slot's Valkey, its turns run at production's pace."""
    system = build_task_system(
        bench.valkey, CollectorRegistry(), TracerProvider(), StreamOptions(consumer="load")
    )
    # Текст пишется в журнал с темпом production, а не ускоренным темпом стенда.
    engine = RunEngine(replace(bench.parts, pace=DEFAULT_PACE))
    system.register([TaskHandler(RUN_TURN, engine.run)])
    bench.queue.sender = system.sender
    return system


async def load(
    bench: TurnBench, asking: list[tuple[uuid.UUID, str]], late: tuple[uuid.UUID, str]
) -> Load:
    """A warm-up turn, then the 48 arriving over `ARRIVALS` and a 49th once they all run."""
    system, (registry, _) = agent_queue(bench), bench.observed
    began: list[None] = []
    database = bench.homes.databases.engine(HOME).sync_engine

    def counted(*_: object) -> None:
        began.append(None)

    async def full() -> bool:
        return int(await bench.valkey.zcard(FLEET_RUNS)) >= CAPACITY

    try:
        async with running(system.brokers[TaskQueue.AGENT], drain=timedelta(seconds=30)):
            # Воркер ходов живёт долго: замер — после первого хода, не на старте потребителя.
            warm = await bench.ask(*late)
            assert warm.status_code == 200, warm.text
            before, cpu = counts(registry, PICKUP), time.process_time()
            event.listen(database, "begin", counted)
            turns = []
            for person, thread in asking:
                turns.append(asyncio.create_task(bench.ask(person, thread)))
                await asyncio.sleep(ARRIVALS / CAPACITY)
            await eventually(full)
            refused = await bench.ask(*late)
            answers = await asyncio.gather(*turns)
            cpu = time.process_time() - cpu
    finally:
        if event.contains(database, "begin", counted):
            event.remove(database, "begin", counted)
    return Load(answers, refused, len(began), cpu, before)


async def recorded_runs(bench: TurnBench, people: list[uuid.UUID]) -> list[DictRow]:
    """The people's runs once every one's end is written: the stream's end comes first."""
    query = "SELECT id, status, overhead_ms FROM agent_runs WHERE user_id = ANY(%s)"

    async def recorded() -> bool:
        rows = await fetch_rows(bench.connection, query, (people,))
        return sum(row["overhead_ms"] is not None for row in rows) == CAPACITY

    await eventually(recorded)
    return await fetch_rows(bench.connection, query, (people,))


async def test_one_agent_worker_answers_48_turns_at_once_within_the_budgets(
    turn_bench: TurnBench,
) -> None:
    people = [uuid.uuid4() for _ in range(CAPACITY)]
    threads = await seed(turn_bench.connection, people)
    late = uuid.uuid4()
    late_thread = await turn_bench.thread(late)
    turn_bench.model.scripts, turn_bench.model.pause = [answering], PAUSE

    done = await load(turn_bench, list(zip(people, threads, strict=True)), (late, late_thread))

    runs = await recorded_runs(turn_bench, people)
    overheads = sorted(int(row["overhead_ms"]) for row in runs)
    p95 = statistics.quantiles(overheads, n=20)[18]
    logs = [int(await turn_bench.valkey.memory_usage(log_key(row["id"])) or 0) for row in runs]
    registry, _ = turn_bench.observed
    pickup = share_within(done.pickup_before, counts(registry, PICKUP), PICKUP_SECONDS)
    log.info(
        "нагрузка хода Leo: %s ходов, время платформы p50 %s мс, p95 %s мс, max %s мс; "
        "подхват очереди ≤ %s с у %.0f %%; журнал в Valkey в среднем %.1f КБ, max %.1f КБ; "
        "транзакций на ход %.1f; процессор стенда (API и воркер в одном цикле) %.0f мс на ход",
        len(runs), statistics.median(overheads), p95, overheads[-1], PICKUP_SECONDS,
        pickup * 100, statistics.mean(logs) / 1024, max(logs) / 1024,
        done.transactions / CAPACITY, done.cpu_seconds * 1000 / CAPACITY,
    )  # fmt: skip
    assert done.refused.status_code == 429, done.refused.text
    assert done.refused.json()["error"]["code"] == "agent_busy"
    assert {answer.status_code for answer in done.answers} == {200}
    assert len(runs) == CAPACITY
    assert {row["status"] for row in runs} == {"completed"}
    assert statistics.median(overheads) <= OVERHEAD_P50_MS
    assert p95 <= OVERHEAD_P95_MS
    assert pickup >= 0.95
    assert max(logs) <= LOG_BYTES
    # Сверх ходов: проверка отказанного 49-го до допуска. Поток читает базу только после 45 с
    # тишины журнала, как в production: на медленной машине CI паузы в секунду бывают у многих
    # потоков сразу, и прежняя секундная тишина стенда добавляла десятки чтений. Лишняя
    # транзакция на ход дала бы 48 сверху.
    assert done.transactions <= TRANSACTIONS_PER_TURN * CAPACITY + CAPACITY // 4
