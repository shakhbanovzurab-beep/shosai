"""Files' tasks: the upload sweep, the purge, the quota pass and the reconciliation.

The scheduler queues one sweep per home every 15 minutes; a pass closes at most a batch
of uploads and retries recorded deletions, and the next pass takes the rest. The purge
removes files hidden for more than 7 days (FL-D5), a batch per home every hour. Once a day
the quota pass takes each person's FL-D2 step, the knowledge pass each person's FL-D10 step,
and the reconciliation reports inv-11. A held image's preview is its own task, queued by its
holder after the commit and again by the sweep while it waits (ADR 0064).
"""

from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Final

from shosai.core.schedule.jobs import PeriodicJob
from shosai.core.tasks.declaration import NO_RETRY, TaskDeclaration, TaskHandler, TaskKind
from shosai.core.tasks.payloads import HomeTaskPayload
from shosai.core.tasks.queues import TaskQueue
from shosai.features.files.application.hidden_files import HiddenFiles
from shosai.features.files.application.leo_sweep import LeoSweep
from shosai.features.files.application.preview_task import MAKE_PREVIEW, PreviewPayload
from shosai.features.files.application.previews import Previews
from shosai.features.files.application.quota_reconciliation import QuotaReconciliation
from shosai.features.files.application.quota_sweep import QuotaSweep
from shosai.features.files.application.upload_sweep import UploadSweep


def tick(name: str, deadline: timedelta) -> TaskDeclaration[HomeTaskPayload]:
    """A per-home tick of files on the bulk queue, not retried: the next tick repeats it."""
    return TaskDeclaration(
        name=name,
        queue=TaskQueue.BULK,
        payload=HomeTaskPayload,
        deadline=deadline,
        retry=NO_RETRY,
        kind=TaskKind.TICK,
    )


SWEEP_UPLOADS: Final = tick("files.sweep_uploads", timedelta(minutes=10))
PURGE_HIDDEN: Final = tick("files.purge_hidden", timedelta(minutes=10))
CHECK_QUOTA: Final = tick("files.check_quota", timedelta(minutes=50))
CHECK_LEO_LIMIT: Final = tick("files.check_leo_limit", timedelta(minutes=50))
RECONCILE_STORAGE: Final = tick("files.reconcile_storage", timedelta(minutes=50))
PERIODIC_JOBS: Final = (
    PeriodicJob(SWEEP_UPLOADS, every=timedelta(minutes=15)),
    PeriodicJob(PURGE_HIDDEN, every=timedelta(hours=1)),
    PeriodicJob(CHECK_QUOTA, every=timedelta(days=1)),
    PeriodicJob(CHECK_LEO_LIMIT, every=timedelta(days=1)),
    PeriodicJob(RECONCILE_STORAGE, every=timedelta(days=1)),
)


@dataclass(frozen=True, slots=True)
class FilesJobs:
    """What files' tasks run."""

    uploads: UploadSweep
    previews: Previews
    hidden: HiddenFiles
    quota: QuotaSweep
    leo: LeoSweep
    reconciliation: QuotaReconciliation


def task_handlers(jobs: FilesJobs) -> tuple[TaskHandler[Any], ...]:
    """The handlers of files' tasks in this process."""

    async def sweep_uploads(payload: HomeTaskPayload) -> None:
        await jobs.uploads.run(payload.home)
        await jobs.previews.retry(payload.home)

    async def make_preview(payload: PreviewPayload) -> None:
        await jobs.previews.make(payload.home, payload.held_id)

    async def purge_hidden(payload: HomeTaskPayload) -> None:
        await jobs.hidden.purge(payload.home)

    async def check_quota(payload: HomeTaskPayload) -> None:
        await jobs.quota.run(payload.home)

    async def check_leo_limit(payload: HomeTaskPayload) -> None:
        await jobs.leo.run(payload.home)

    async def reconcile_storage(payload: HomeTaskPayload) -> None:
        await jobs.reconciliation.run(payload.home)

    return (
        TaskHandler(SWEEP_UPLOADS, sweep_uploads),
        TaskHandler(MAKE_PREVIEW, make_preview),
        TaskHandler(PURGE_HIDDEN, purge_hidden),
        TaskHandler(CHECK_QUOTA, check_quota),
        TaskHandler(CHECK_LEO_LIMIT, check_leo_limit),
        TaskHandler(RECONCILE_STORAGE, reconcile_storage),
    )
