"""The tasks of transfers: the due sweep, the saga run and the purge of old journals (§6)."""

from datetime import UTC, datetime, timedelta
from typing import Any, Final
from uuid import UUID

from shosai.core.db.transactions import HomeTransactions
from shosai.core.schedule.jobs import DueRowSource, PeriodicJob
from shosai.core.tasks.declaration import (
    NO_RETRY,
    TRANSIENT_FAILURES,
    RetryPolicy,
    TaskDeclaration,
    TaskHandler,
    TaskKind,
)
from shosai.core.tasks.payloads import HomeTaskPayload
from shosai.core.tasks.queues import TaskQueue
from shosai.core.tasks.sender import TaskSender
from shosai.features.identity.application.transfer_saga import TransferSaga
from shosai.features.identity.infrastructure.transfer_journal import purge_finished

# Журнал законченного переноса — запись о нём; хранится 30 дней, как строка каталога.
FINISHED_KEPT: Final = timedelta(days=30)


class TransferPayload(HomeTaskPayload):
    """The transfer the task runs; `home` is where its journal lives."""

    transfer_id: UUID


TRANSFER_DUE: Final = TaskDeclaration(
    name="identity.transfer_due",
    queue=TaskQueue.DEFAULT,
    payload=HomeTaskPayload,
    deadline=timedelta(minutes=1),
    retry=NO_RETRY,
    kind=TaskKind.TICK,
)
RUN_TRANSFER: Final = TaskDeclaration(
    name="identity.run_transfer",
    queue=TaskQueue.BULK,
    payload=TransferPayload,
    deadline=timedelta(minutes=25),
    retry=RetryPolicy(max_deliveries=5, retry_on=TRANSIENT_FAILURES),
    kind=TaskKind.WORK,
)
PURGE_TRANSFERS: Final = TaskDeclaration(
    name="identity.purge_transfers",
    queue=TaskQueue.BULK,
    payload=HomeTaskPayload,
    deadline=timedelta(minutes=5),
    retry=NO_RETRY,
    kind=TaskKind.TICK,
)
TRANSFER_SOURCES: Final = (DueRowSource(TRANSFER_DUE, every=timedelta(seconds=15)),)
TRANSFER_JOBS: Final = (PeriodicJob(PURGE_TRANSFERS, every=timedelta(days=1)),)


def transfer_task_handlers(
    saga: TransferSaga, transactions: HomeTransactions, tasks: TaskSender
) -> tuple[TaskHandler[Any], ...]:
    """The transfer tasks bound to the process."""

    async def transfer_due(payload: HomeTaskPayload) -> None:
        for transfer_id in await saga.start_due(payload.home):
            await tasks.send(
                RUN_TRANSFER, TransferPayload(home=payload.home, transfer_id=transfer_id)
            )

    async def run_transfer(payload: TransferPayload) -> None:
        await saga.run(payload.home, payload.transfer_id)

    async def purge_transfers(payload: HomeTaskPayload) -> None:
        await purge_finished(transactions, payload.home, datetime.now(UTC) - FINISHED_KEPT)

    return (
        TaskHandler(TRANSFER_DUE, transfer_due),
        TaskHandler(RUN_TRANSFER, run_transfer),
        TaskHandler(PURGE_TRANSFERS, purge_transfers),
    )
