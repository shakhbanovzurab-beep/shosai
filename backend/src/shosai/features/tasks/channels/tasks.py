"""Tasks' tick: giving the objects of deleted attachments back to files (ADR 0064 point 6).

The scheduler queues one tick per home every 15 minutes; a pass gives back a batch, and the
next pass takes the rest. Deletions made through tasks' own routes give theirs back right
after their commit; the tick covers cascades and anything a failure left.
"""

from datetime import timedelta
from typing import Any, Final

from shosai.core.schedule.jobs import PeriodicJob
from shosai.core.tasks.declaration import NO_RETRY, TaskDeclaration, TaskHandler, TaskKind
from shosai.core.tasks.payloads import HomeTaskPayload
from shosai.core.tasks.queues import TaskQueue
from shosai.features.tasks.application.attachment_releases import TICK_EVERY, AttachmentReleases

RELEASE_ATTACHMENTS: Final = TaskDeclaration(
    name="tasks.release_attachments",
    queue=TaskQueue.BULK,
    payload=HomeTaskPayload,
    deadline=timedelta(minutes=10),
    retry=NO_RETRY,
    kind=TaskKind.TICK,
)
PERIODIC_JOBS: Final = (PeriodicJob(RELEASE_ATTACHMENTS, every=TICK_EVERY),)


def task_handlers(releases: AttachmentReleases) -> tuple[TaskHandler[Any], ...]:
    """The handlers of tasks' tasks in this process."""

    async def release_attachments(payload: HomeTaskPayload) -> None:
        await releases.drain(payload.home)

    return (TaskHandler(RELEASE_ATTACHMENTS, release_attachments),)
