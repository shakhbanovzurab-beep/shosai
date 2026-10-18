"""Files' tasks: the sweep of expired uploads and waiting deletions, and the purge.

The scheduler queues one sweep per home every 15 minutes; a pass closes at most a batch
of uploads and retries recorded deletions, and the next pass takes the rest. The purge
removes files hidden for more than 7 days (FL-D5), a batch per home every hour.
"""

from datetime import timedelta
from typing import Any, Final

from shosai.core.schedule.jobs import PeriodicJob
from shosai.core.tasks.declaration import NO_RETRY, TaskDeclaration, TaskHandler, TaskKind
from shosai.core.tasks.payloads import HomeTaskPayload
from shosai.core.tasks.queues import TaskQueue
from shosai.features.files.application.hidden_files import HiddenFiles
from shosai.features.files.application.upload_sweep import UploadSweep

SWEEP_UPLOADS: Final = TaskDeclaration(
    name="files.sweep_uploads",
    queue=TaskQueue.BULK,
    payload=HomeTaskPayload,
    deadline=timedelta(minutes=10),
    retry=NO_RETRY,
    kind=TaskKind.TICK,
)
PURGE_HIDDEN: Final = TaskDeclaration(
    name="files.purge_hidden",
    queue=TaskQueue.BULK,
    payload=HomeTaskPayload,
    deadline=timedelta(minutes=10),
    retry=NO_RETRY,
    kind=TaskKind.TICK,
)
PERIODIC_JOBS: Final = (
    PeriodicJob(SWEEP_UPLOADS, every=timedelta(minutes=15)),
    PeriodicJob(PURGE_HIDDEN, every=timedelta(hours=1)),
)


def task_handlers(sweep: UploadSweep, hidden: HiddenFiles) -> tuple[TaskHandler[Any], ...]:
    """The handlers of files' tasks in this process."""

    async def sweep_uploads(payload: HomeTaskPayload) -> None:
        await sweep.run(payload.home)

    async def purge_hidden(payload: HomeTaskPayload) -> None:
        await hidden.purge(payload.home)

    return (TaskHandler(SWEEP_UPLOADS, sweep_uploads), TaskHandler(PURGE_HIDDEN, purge_hidden))
