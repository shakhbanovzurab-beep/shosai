"""Memory's periodic work: the embedding pass of each home, once a minute (memory step 4).

A fact written without a vector is recalled from the next minute on; a pass lost or repeated
changes nothing the next one would not, since a vector lands only on a fact still waiting for
one.
"""

from datetime import timedelta
from typing import Final

from shosai.core.schedule.jobs import PeriodicJob
from shosai.core.tasks.declaration import NO_RETRY, TaskDeclaration, TaskHandler, TaskKind
from shosai.core.tasks.payloads import HomeTaskPayload
from shosai.core.tasks.queues import TaskQueue
from shosai.features.memory.application.embedding_pass import EmbeddingPass

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
