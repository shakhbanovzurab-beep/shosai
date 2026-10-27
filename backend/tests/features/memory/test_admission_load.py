"""One `default` worker taking turns' admissions (memory step 11, plan §1.3).

The extraction double answers after 1.5 s — a flash-class model's first token and 150 tokens at
100 a second — and the embedding double after 0.3 s, so an admission holds one of the worker's
slots about 1.8 s, and no database connection while it waits. Forty turns end at once and go
through the real `default` queue on the slot's Valkey to one consumer with the queue's
production profile. The worker admits them close to its slots over that time — the capacity
the plan sizes the `default` workers by — and every one within the ticket's minute. The numbers
are logged for the plan (`--log-cli-level=INFO`).
"""

import logging
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Final

from opentelemetry.sdk.trace import TracerProvider
from prometheus_client import CollectorRegistry
from redis.asyncio import Redis

from shosai.core.kernel.homes import Home
from shosai.core.tasks.queues import QUEUE_PROFILES, TaskQueue
from shosai.core.tasks.system import StreamOptions, build_task_system
from shosai.features.memory.channels.tasks import ADMIT_TURN, TurnTask, turn_admission
from shosai.features.memory.infrastructure.metrics import ADMISSION_LAG
from tests.core.tasks.workbench import eventually, running
from tests.features.memory.admission_bench import AdmissionBench, said
from tests.features.memory.recall_bench import axis

log = logging.getLogger(__name__)

TURNS: Final = 40
EXTRACTION: Final = timedelta(seconds=1.5)
EMBEDDING: Final = timedelta(seconds=0.3)
SLOTS: Final = QUEUE_PROFILES[TaskQueue.DEFAULT].concurrency
HOLD: Final = (EXTRACTION + EMBEDDING).total_seconds()
# Предел стенда: четыре пятых расчётной пропускной способности слотов.
SHARE_OF_CAPACITY: Final = 0.8
TICKET: Final = "60.0"


async def test_one_default_worker_admits_at_its_slots_pace_within_the_ticket(
    admission_bench: AdmissionBench, valkey: Redis
) -> None:
    people = [uuid.uuid4() for _ in range(TURNS)]
    admission_bench.consents.given |= set(people)
    admission_bench.vectors.known["Works late"] = axis(1)
    admission_bench.vectors.delay = EMBEDDING
    admission_bench.statements.found = [said("Works late")]
    admission_bench.statements.delay = EXTRACTION
    system = build_task_system(
        valkey, CollectorRegistry(), TracerProvider(), StreamOptions(consumer="load")
    )
    system.register([turn_admission(admission_bench.admission)])
    sample = admission_bench.registry.get_sample_value

    async def admitted() -> bool:
        return sample(f"{ADMISSION_LAG}_count") == TURNS

    async with running(system.brokers[TaskQueue.DEFAULT], drain=timedelta(seconds=10)):
        started, ended = time.monotonic(), datetime.now(UTC)
        for person in people:
            run = admission_bench.turns.said("I work late a lot.")
            payload = TurnTask(home=Home.RU, user_id=person, run_id=run, ended_at=ended)
            await system.sender.send(ADMIT_TURN, payload)
        await eventually(admitted, within=60)
        took = time.monotonic() - started

    pace, capacity = TURNS / took, SLOTS / HOLD
    mean_lag = (sample(f"{ADMISSION_LAG}_sum") or 0) / TURNS
    log.info(
        "приём ходов одним воркером default: %s ходов за %.1f с, %.2f в секунду при расчётных "
        "%.2f (%s слотов по %.1f с); задержка в среднем %.1f с, последняя %.1f с",
        TURNS, took, pace, capacity, SLOTS, HOLD, mean_lag, took,
    )  # fmt: skip
    assert sample(f"{ADMISSION_LAG}_bucket", {"le": TICKET}) == TURNS
    assert pace >= capacity * SHARE_OF_CAPACITY, f"{pace:.2f} в секунду"
    assert [await admission_bench.embedded(person) for person in people] == [1] * TURNS
