"""Identity's periodic tasks: the sweeps behind registration (identity plan §3.6).

The hourly directory check settles the stale claims first, so a claim the 5-minute sweep
has not reached yet is never counted as an address without an account (inv-1).
"""

from datetime import timedelta
from typing import Any, Final

from prometheus_client import CollectorRegistry

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.schedule.jobs import PeriodicJob
from shosai.core.tasks.declaration import NO_RETRY, TaskDeclaration, TaskHandler, TaskKind
from shosai.core.tasks.payloads import HomeTaskPayload
from shosai.core.tasks.queues import TaskQueue
from shosai.features.identity.application.directory_check import DirectoryCheck
from shosai.features.identity.application.sweeps import (
    CLAIMS_PER_SWEEP,
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
CHECK_DIRECTORY: Final = TaskDeclaration(
    name="identity.check_directory",
    queue=TaskQueue.BULK,
    payload=HomeTaskPayload,
    deadline=timedelta(minutes=10),
    retry=NO_RETRY,
    kind=TaskKind.TICK,
)
# Каталог живёт в доме ЕС: обход заявок идёт оттуда и заглядывает в оба дома.
PERIODIC_JOBS: Final = (
    PeriodicJob(PURGE_PENDING, every=timedelta(minutes=10)),
    PeriodicJob(SETTLE_CLAIMS, every=timedelta(minutes=5), homes=(Home.EU,)),
    PeriodicJob(PURGE_SESSIONS, every=timedelta(days=1)),
    PeriodicJob(CHECK_DIRECTORY, every=timedelta(hours=1), homes=(Home.EU,)),
)


def task_handlers(
    transactions: HomeTransactions, directory: Directory, registry: CollectorRegistry
) -> tuple[TaskHandler[Any], ...]:
    """The sweeps bound to the process, the directory check with its gauge."""
    check = DirectoryCheck(transactions, registry)

    async def purge(payload: HomeTaskPayload) -> None:
        await purge_pending(transactions, payload.home)

    async def settle(_payload: HomeTaskPayload) -> None:
        await settle_claims(transactions, directory)

    async def purge_ended(payload: HomeTaskPayload) -> None:
        await purge_sessions(transactions, payload.home)

    async def check_directory(_payload: HomeTaskPayload) -> None:
        while await settle_claims(transactions, directory) == CLAIMS_PER_SWEEP:
            continue
        await check.run()

    return (
        TaskHandler(PURGE_PENDING, purge),
        TaskHandler(SETTLE_CLAIMS, settle),
        TaskHandler(PURGE_SESSIONS, purge_ended),
        TaskHandler(CHECK_DIRECTORY, check_directory),
    )
