"""The purge task of the effect keys: a tick per home once a day, in every role (§14 rule 9)."""

from datetime import timedelta
from typing import Any, Final

from shosai.core.db.transactions import HomeTransactions
from shosai.core.idempotency.metrics import EffectKeyMetrics
from shosai.core.idempotency.purge import EffectKeyPurge
from shosai.core.tasks.declaration import NO_RETRY, TaskDeclaration, TaskHandler, TaskKind
from shosai.core.tasks.payloads import HomeTaskPayload
from shosai.core.tasks.queues import TaskQueue

PURGE_KEYS_EVERY: Final = timedelta(days=1)
PURGE_EFFECT_KEYS: Final = TaskDeclaration(
    name="idempotency.purge_keys",
    queue=TaskQueue.BULK,
    payload=HomeTaskPayload,
    deadline=timedelta(minutes=10),
    retry=NO_RETRY,
    kind=TaskKind.TICK,
)


def effect_key_task_handlers(
    transactions: HomeTransactions, metrics: EffectKeyMetrics
) -> list[TaskHandler[Any]]:
    """The purge task bound to the process."""
    purge = EffectKeyPurge(transactions, metrics)

    async def purge_keys(payload: HomeTaskPayload) -> None:
        await purge.purge(payload.home)

    return [TaskHandler(PURGE_EFFECT_KEYS, purge_keys)]
