"""Meetings' tasks: a run's stages, the minute ticks of the sweeps and the hourly purge (4, 5, 8).

A stage is a task of the `meeting` queue (`application/stage_task.py`). The sweeps — the
forgotten meetings, the ended ones, the lost stages of runs — are ticks of the default
queue, not retried: the next minute's tick repeats them, and a pass takes at most a
batch, leaving the rest to the next one.
"""

from datetime import timedelta
from typing import Any, Final

from shosai.core.schedule.jobs import PeriodicJob
from shosai.core.tasks.declaration import NO_RETRY, TaskDeclaration, TaskHandler, TaskKind
from shosai.core.tasks.payloads import HomeTaskPayload
from shosai.core.tasks.queues import TaskQueue
from shosai.features.meetings.application.hidden_meetings import HiddenMeetings
from shosai.features.meetings.application.pipeline import PipelineEngine
from shosai.features.meetings.application.run_recovery import RunRecovery
from shosai.features.meetings.application.stage_task import RUN_STAGE, StagePayload
from shosai.features.meetings.application.sweeps import MeetingSweeps


def tick(
    name: str, deadline: timedelta = timedelta(seconds=50)
) -> TaskDeclaration[HomeTaskPayload]:
    """A per-home tick of meetings, not retried: the next one repeats it."""
    return TaskDeclaration(
        name=name,
        queue=TaskQueue.DEFAULT,
        payload=HomeTaskPayload,
        deadline=deadline,
        retry=NO_RETRY,
        kind=TaskKind.TICK,
    )


END_FORGOTTEN: Final = tick("meetings.end_forgotten")
SETTLE_ENDED: Final = tick("meetings.settle_ended")
RECOVER_RUNS: Final = tick("meetings.recover_runs")
PURGE_HIDDEN: Final = tick("meetings.purge_hidden", timedelta(minutes=10))
PERIODIC_JOBS: Final = (
    PeriodicJob(END_FORGOTTEN, every=timedelta(minutes=1)),
    PeriodicJob(SETTLE_ENDED, every=timedelta(minutes=1)),
    PeriodicJob(RECOVER_RUNS, every=timedelta(minutes=1)),
    PeriodicJob(PURGE_HIDDEN, every=timedelta(hours=1)),
)


def task_handlers(
    sweeps: tuple[MeetingSweeps, HiddenMeetings], pipeline: tuple[PipelineEngine, RunRecovery]
) -> tuple[TaskHandler[Any], ...]:
    """The handlers of meetings' tasks in this process."""
    live, hidden = sweeps
    engine, recovery = pipeline

    async def end_forgotten(payload: HomeTaskPayload) -> None:
        await live.end_forgotten(payload.home)

    async def settle_ended(payload: HomeTaskPayload) -> None:
        await live.settle(payload.home)

    async def recover_runs(payload: HomeTaskPayload) -> None:
        await recovery.run(payload.home)

    async def run_stage(payload: StagePayload) -> None:
        await engine.run_stage(payload)

    async def purge_hidden(payload: HomeTaskPayload) -> None:
        await hidden.purge(payload.home)

    return (
        TaskHandler(END_FORGOTTEN, end_forgotten),
        TaskHandler(SETTLE_ENDED, settle_ended),
        TaskHandler(RECOVER_RUNS, recover_runs),
        TaskHandler(RUN_STAGE, run_stage),
        TaskHandler(PURGE_HIDDEN, purge_hidden),
    )
