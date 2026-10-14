"""Identity's periodic tasks: the sweeps behind registration (identity plan §3.6)."""

from datetime import timedelta
from typing import Any, Final

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.schedule.jobs import PeriodicJob
from shosai.core.tasks.declaration import NO_RETRY, TaskDeclaration, TaskHandler, TaskKind
from shosai.core.tasks.payloads import HomeTaskPayload
from shosai.core.tasks.queues import TaskQueue
from shosai.features.identity.application.sweeps import (
    purge_pending,
    purge_sessions,
    settle_claims,
)
from shosai.features.identity.infrastructure.directory import Directory

PURGE_PENDING: Final = TaskDeclaration(
    name="identity.purge_pending",
    queue=TaskQueue.BULK,
    payload=HomeTaskPayload,
    deadline=timedelta(minutes=2),
    retry=NO_RETRY,
    kind=TaskKind.TICK,
)
SETTLE_CLAIMS: Final = TaskDeclaration(
    name="identity.settle_claims",
    queue=TaskQueue.DEFAULT,
    payload=HomeTaskPayload,
    deadline=timedelta(minutes=2),
    retry=NO_RETRY,
    kind=TaskKind.TICK,
)
PURGE_SESSIONS: Final = TaskDeclaration(
    name="identity.purge_sessions",
    queue=TaskQueue.BULK,
    payload=HomeTaskPayload,
    deadline=timedelta(minutes=5),
    retry=NO_RETRY,
    kind=TaskKind.TICK,
)
# Каталог живёт в доме ЕС: обход заявок идёт оттуда и заглядывает в оба дома.
PERIODIC_JOBS: Final = (
    PeriodicJob(PURGE_PENDING, every=timedelta(minutes=10)),
    PeriodicJob(SETTLE_CLAIMS, every=timedelta(minutes=5), homes=(Home.EU,)),
    PeriodicJob(PURGE_SESSIONS, every=timedelta(days=1)),
)


def task_handlers(
    transactions: HomeTransactions, directory: Directory
) -> tuple[TaskHandler[Any], ...]:
    """The sweeps bound to the process."""

    async def purge(payload: HomeTaskPayload) -> None:
        await purge_pending(transactions, payload.home)

    async def settle(_payload: HomeTaskPayload) -> None:
        await settle_claims(transactions, directory)

    async def purge_ended(payload: HomeTaskPayload) -> None:
        await purge_sessions(transactions, payload.home)

    return (
        TaskHandler(PURGE_PENDING, purge),
        TaskHandler(SETTLE_CLAIMS, settle),
        TaskHandler(PURGE_SESSIONS, purge_ended),
    )
