"""Memory's tasks: a turn's admission after `agent.turn.completed` (step 5), and the embedding
pass of each home, once a minute (step 4).

A fact written without a vector is recalled from the next minute on; a pass lost or repeated
changes nothing the next one would not, since a vector lands only on a fact still waiting for
one.
"""

from datetime import timedelta
from typing import Final
from uuid import UUID

from shosai.core.ai.errors import AiCallError
from shosai.core.schedule.jobs import PeriodicJob
from shosai.core.tasks.declaration import (
    MAX_DELIVERIES,
    NO_RETRY,
    TRANSIENT_FAILURES,
    RetryPolicy,
    TaskDeclaration,
    TaskHandler,
    TaskKind,
)
from shosai.core.tasks.payloads import HomeTaskPayload
from shosai.core.tasks.queues import TaskQueue
from shosai.features.memory.application.embedding_pass import EmbeddingPass
from shosai.features.memory.application.turn_admission import TurnAdmission


class TurnTask(HomeTaskPayload):
    """One finished turn of a person."""

    run_id: UUID


# Сбой поставщика модели — тоже повод повторить: запись приёма идемпотентна по прогону.
ADMIT_TURN: Final = TaskDeclaration(
    name="memory.admit_turn",
    queue=TaskQueue.DEFAULT,
    payload=TurnTask,
    deadline=timedelta(minutes=3),
    retry=RetryPolicy(MAX_DELIVERIES, (*TRANSIENT_FAILURES, AiCallError)),
)
EMBED_WAITING: Final = TaskDeclaration(
    name="memory.embed_waiting",
    queue=TaskQueue.DEFAULT,
    payload=HomeTaskPayload,
    deadline=timedelta(minutes=2),
    retry=NO_RETRY,
    kind=TaskKind.TICK,
)
PERIODIC_JOBS: Final = (PeriodicJob(EMBED_WAITING, every=timedelta(minutes=1)),)


def embedding_tick(embedding: EmbeddingPass) -> TaskHandler[HomeTaskPayload]:
    """The pass of the payload's home."""

    async def embed(payload: HomeTaskPayload) -> None:
        await embedding.run(payload.home)

    return TaskHandler(EMBED_WAITING, embed)


def turn_admission(admission: TurnAdmission) -> TaskHandler[TurnTask]:
    """The admission of the payload's turn."""

    async def admit(payload: TurnTask) -> None:
        if payload.user_id is not None:
            await admission.admit(payload.home, payload.user_id, payload.run_id)

    return TaskHandler(ADMIT_TURN, admit)
