"""The slice's tasks: a run's stages, the minute ticks of the sweeps and the hourly purge (4, 5, 8).

A stage is a task of the `meeting` queue (`application/stage_task.py`). The sweeps — the
forgotten meetings, the ended ones, the lost stages of runs — are ticks of the default
queue, not retried: the next minute's tick repeats them, and a pass takes at most a
batch, leaving the rest to the next one. The transcript archive (step 20) is a minute tick
of the bulk queue: a month of the design point, some 600 000 meetings, goes in about four
days.
"""

from datetime import timedelta
from typing import Any, Final

from shosai.core.schedule.jobs import PeriodicJob
from shosai.core.tasks.declaration import NO_RETRY, TaskDeclaration, TaskHandler, TaskKind
from shosai.core.tasks.payloads import HomeTaskPayload
from shosai.core.tasks.queues import TaskQueue
from shosai.features.notes.application.hidden_meetings import HiddenMeetings
from shosai.features.notes.application.pipeline import PipelineEngine
from shosai.features.notes.application.run_recovery import RunRecovery
from shosai.features.notes.application.stage_task import RUN_STAGE, StagePayload
from shosai.features.notes.application.sweeps import MeetingSweeps
from shosai.features.notes.application.transcript_archiver import TranscriptArchiver


def tick(
    name: str, deadline: timedelta = timedelta(seconds=50), queue: TaskQueue = TaskQueue.DEFAULT
) -> TaskDeclaration[HomeTaskPayload]:
    """A per-home tick of meetings, not retried: the next one repeats it."""
    return TaskDeclaration(
        name=name,
        queue=queue,
        payload=HomeTaskPayload,
        deadline=deadline,
        retry=NO_RETRY,
        kind=TaskKind.TICK,
    )


END_FORGOTTEN: Final = tick("notes.end_forgotten")
SETTLE_ENDED: Final = tick("notes.settle_ended")
RECOVER_RUNS: Final = tick("notes.recover_runs")
PURGE_HIDDEN: Final = tick("notes.purge_hidden", timedelta(minutes=10))
ARCHIVE_TRANSCRIPTS: Final = tick("notes.archive_transcripts", queue=TaskQueue.BULK)
PERIODIC_JOBS: Final = (
    PeriodicJob(END_FORGOTTEN, every=timedelta(minutes=1)),
    PeriodicJob(SETTLE_ENDED, every=timedelta(minutes=1)),
    PeriodicJob(RECOVER_RUNS, every=timedelta(minutes=1)),
    PeriodicJob(PURGE_HIDDEN, every=timedelta(hours=1)),
    PeriodicJob(ARCHIVE_TRANSCRIPTS, every=timedelta(minutes=1)),
)


def task_handlers(
    sweeps: tuple[MeetingSweeps, HiddenMeetings, TranscriptArchiver],
    pipeline: tuple[PipelineEngine, RunRecovery],
) -> tuple[TaskHandler[Any], ...]:
    """The handlers of the slice's tasks in this process."""
    live, hidden, archiver = sweeps
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

    async def archive_transcripts(payload: HomeTaskPayload) -> None:
        await archiver.run(payload.home)

    return (
        TaskHandler(END_FORGOTTEN, end_forgotten),
        TaskHandler(SETTLE_ENDED, settle_ended),
        TaskHandler(RECOVER_RUNS, recover_runs),
        TaskHandler(RUN_STAGE, run_stage),
        TaskHandler(PURGE_HIDDEN, purge_hidden),
        TaskHandler(ARCHIVE_TRANSCRIPTS, archive_transcripts),
    )
