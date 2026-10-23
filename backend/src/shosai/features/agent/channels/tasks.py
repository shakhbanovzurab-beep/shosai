"""The slice's tasks (agent plan §3.1): so far the hourly purge of departed workspaces' threads
(step 4), a per-home tick that is not retried — the next hour repeats it, and a pass takes at
most a batch. The run and resume tasks on the `agent` queue and the sweeps join with step 5a."""

from datetime import timedelta
from typing import Any, Final

from shosai.core.schedule.jobs import PeriodicJob
from shosai.core.tasks.declaration import NO_RETRY, TaskDeclaration, TaskHandler, TaskKind
from shosai.core.tasks.payloads import HomeTaskPayload
from shosai.core.tasks.queues import TaskQueue
from shosai.features.agent.application.departures import Departures

PURGE_DEPARTED: Final = TaskDeclaration(
    name="agent.purge_departed",
    queue=TaskQueue.DEFAULT,
    payload=HomeTaskPayload,
    deadline=timedelta(minutes=5),
    retry=NO_RETRY,
    kind=TaskKind.TICK,
)
PERIODIC_JOBS: Final = (PeriodicJob(PURGE_DEPARTED, every=timedelta(hours=1)),)


def task_handlers(departures: Departures) -> tuple[TaskHandler[Any], ...]:
    """The handlers of the slice's tasks in this process."""

    async def purge_departed(payload: HomeTaskPayload) -> None:
        await departures.purge(payload.home)

    return (TaskHandler(PURGE_DEPARTED, purge_departed),)
