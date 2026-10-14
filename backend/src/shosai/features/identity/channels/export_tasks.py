"""The tasks of export: the due sweep, the making of an archive and the daily purge."""

from datetime import timedelta
from typing import Any, Final
from uuid import UUID

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
from shosai.features.identity.application.export_runner import ExportRunner


class ExportPayload(HomeTaskPayload):
    """The job whose archive the task makes."""

    job_id: UUID


EXPORT_DUE: Final = TaskDeclaration(
    name="identity.export_due",
    queue=TaskQueue.DEFAULT,
    payload=HomeTaskPayload,
    deadline=timedelta(minutes=1),
    retry=NO_RETRY,
    kind=TaskKind.TICK,
)
MAKE_EXPORT: Final = TaskDeclaration(
    name="identity.make_export",
    queue=TaskQueue.BULK,
    payload=ExportPayload,
    deadline=timedelta(minutes=40),
    retry=RetryPolicy(max_deliveries=5, retry_on=TRANSIENT_FAILURES),
    kind=TaskKind.WORK,
)
PURGE_EXPORTS: Final = TaskDeclaration(
    name="identity.purge_exports",
    queue=TaskQueue.BULK,
    payload=HomeTaskPayload,
    deadline=timedelta(minutes=10),
    retry=NO_RETRY,
    kind=TaskKind.TICK,
)
EXPORT_SOURCES: Final = (DueRowSource(EXPORT_DUE, every=timedelta(seconds=15)),)
EXPORT_JOBS: Final = (PeriodicJob(PURGE_EXPORTS, every=timedelta(hours=1)),)


def export_task_handlers(runner: ExportRunner, tasks: TaskSender) -> tuple[TaskHandler[Any], ...]:
    """The export tasks bound to the process."""

    async def export_due(payload: HomeTaskPayload) -> None:
        for job_id in await runner.start_due(payload.home):
            await tasks.send(MAKE_EXPORT, ExportPayload(home=payload.home, job_id=job_id))

    async def make_export(payload: ExportPayload) -> None:
        await runner.make(payload.home, payload.job_id)

    async def purge_exports(payload: HomeTaskPayload) -> None:
        await runner.purge(payload.home)

    return (
        TaskHandler(EXPORT_DUE, export_due),
        TaskHandler(MAKE_EXPORT, make_export),
        TaskHandler(PURGE_EXPORTS, purge_exports),
    )
