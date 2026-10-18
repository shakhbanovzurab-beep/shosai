"""Files' tasks: the sweep of expired uploads and of objects waiting for deletion.

The scheduler queues one sweep per home every 15 minutes; a pass closes at most a batch
of uploads and retries recorded deletions, and the next pass takes the rest.
"""

from datetime import timedelta
from typing import Any, Final

from shosai.core.schedule.jobs import PeriodicJob
from shosai.core.tasks.declaration import NO_RETRY, TaskDeclaration, TaskHandler, TaskKind
from shosai.core.tasks.payloads import HomeTaskPayload
from shosai.core.tasks.queues import TaskQueue
from shosai.features.files.application.upload_sweep import UploadSweep

SWEEP_UPLOADS: Final = TaskDeclaration(
    name="files.sweep_uploads",
    queue=TaskQueue.BULK,
    payload=HomeTaskPayload,
    deadline=timedelta(minutes=10),
    retry=NO_RETRY,
    kind=TaskKind.TICK,
)
PERIODIC_JOBS: Final = (PeriodicJob(SWEEP_UPLOADS, every=timedelta(minutes=15)),)


def task_handlers(sweep: UploadSweep) -> tuple[TaskHandler[Any], ...]:
    """The handlers of files' tasks in this process."""

    async def sweep_uploads(payload: HomeTaskPayload) -> None:
        await sweep.run(payload.home)

    return (TaskHandler(SWEEP_UPLOADS, sweep_uploads),)
