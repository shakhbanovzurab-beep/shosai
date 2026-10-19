"""Meetings' tasks: the live sweep and the settle sweep, every minute per home (plan step 4).

Both are ticks of the default queue, not retried: the next minute's tick repeats them, and
a pass takes at most a batch, leaving the rest to the next one.
"""

from datetime import timedelta
from typing import Any, Final

from shosai.core.schedule.jobs import PeriodicJob
from shosai.core.tasks.declaration import NO_RETRY, TaskDeclaration, TaskHandler, TaskKind
from shosai.core.tasks.payloads import HomeTaskPayload
from shosai.core.tasks.queues import TaskQueue
from shosai.features.meetings.application.sweeps import MeetingSweeps


def tick(name: str) -> TaskDeclaration[HomeTaskPayload]:
    """A per-home minute tick of meetings, not retried."""
    return TaskDeclaration(
        name=name,
        queue=TaskQueue.DEFAULT,
        payload=HomeTaskPayload,
        deadline=timedelta(seconds=50),
        retry=NO_RETRY,
        kind=TaskKind.TICK,
    )


END_FORGOTTEN: Final = tick("meetings.end_forgotten")
SETTLE_ENDED: Final = tick("meetings.settle_ended")
PERIODIC_JOBS: Final = (
    PeriodicJob(END_FORGOTTEN, every=timedelta(minutes=1)),
    PeriodicJob(SETTLE_ENDED, every=timedelta(minutes=1)),
)


def task_handlers(sweeps: MeetingSweeps) -> tuple[TaskHandler[Any], ...]:
    """The handlers of meetings' tasks in this process."""

    async def end_forgotten(payload: HomeTaskPayload) -> None:
        await sweeps.end_forgotten(payload.home)

    async def settle_ended(payload: HomeTaskPayload) -> None:
        await sweeps.settle(payload.home)

    return (TaskHandler(END_FORGOTTEN, end_forgotten), TaskHandler(SETTLE_ENDED, settle_ended))
