"""The partition upkeep task: a tick per home once a day, in every role (§14 rule 9)."""

from datetime import timedelta
from typing import Any, Final

from shosai.core.db.partitions.upkeep import PartitionMetrics, PartitionUpkeep
from shosai.core.db.transactions import HomeTransactions
from shosai.core.tasks.declaration import NO_RETRY, TaskDeclaration, TaskHandler, TaskKind
from shosai.core.tasks.payloads import HomeTaskPayload
from shosai.core.tasks.queues import TaskQueue

# Партиции создаются на два месяца вперёд: суточный такт успевает с большим запасом.
MAINTAIN_EVERY: Final = timedelta(days=1)
MAINTAIN_PARTITIONS: Final = TaskDeclaration(
    name="db.maintain_partitions",
    queue=TaskQueue.BULK,
    payload=HomeTaskPayload,
    deadline=timedelta(minutes=5),
    retry=NO_RETRY,
    kind=TaskKind.TICK,
)


def partition_task_handlers(
    transactions: HomeTransactions, metrics: PartitionMetrics
) -> list[TaskHandler[Any]]:
    """The upkeep task bound to the process."""
    upkeep = PartitionUpkeep(transactions, metrics)

    async def maintain_partitions(payload: HomeTaskPayload) -> None:
        await upkeep.maintain(payload.home)

    return [TaskHandler(MAINTAIN_PARTITIONS, maintain_partitions)]
