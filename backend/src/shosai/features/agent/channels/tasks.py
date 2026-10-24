"""The slice's tasks (agent plan §3.1): Leo's turns on the `agent` queue, a minute's sweep of
lost runs and the hourly purge of departed workspaces' threads.

A turn is never retried by the queue (`application/turn_task.py`); the sweep and the purge are
per-home ticks that are not retried either — the next tick repeats them, and a pass takes at
most a batch.
"""

from datetime import timedelta
from typing import Any, Final

from shosai.core.schedule.jobs import PeriodicJob
from shosai.core.tasks.declaration import NO_RETRY, TaskDeclaration, TaskHandler, TaskKind
from shosai.core.tasks.payloads import HomeTaskPayload
from shosai.core.tasks.queues import TaskQueue
from shosai.features.agent.application.departures import Departures
from shosai.features.agent.application.lost_runs import LostRuns
from shosai.features.agent.application.run_engine import RunEngine
from shosai.features.agent.application.turn_task import RUN_TURN, TurnPayload


def tick(name: str, deadline: timedelta) -> TaskDeclaration[HomeTaskPayload]:
    """A per-home tick of the default queue, not retried: the next one repeats it."""
    return TaskDeclaration(
        name=name,
        queue=TaskQueue.DEFAULT,
        payload=HomeTaskPayload,
        deadline=deadline,
        retry=NO_RETRY,
        kind=TaskKind.TICK,
    )


PURGE_DEPARTED: Final = tick("agent.purge_departed", timedelta(minutes=5))
SWEEP_LOST_RUNS: Final = tick("agent.sweep_lost_runs", timedelta(seconds=50))
PERIODIC_JOBS: Final = (
    PeriodicJob(PURGE_DEPARTED, every=timedelta(hours=1)),
    PeriodicJob(SWEEP_LOST_RUNS, every=timedelta(minutes=1)),
)


def task_handlers(
    departures: Departures, lost_runs: LostRuns, engine: RunEngine
) -> tuple[TaskHandler[Any], ...]:
    """The handlers of the slice's tasks in this process."""

    async def purge_departed(payload: HomeTaskPayload) -> None:
        await departures.purge(payload.home)

    async def sweep_lost_runs(payload: HomeTaskPayload) -> None:
        await lost_runs.sweep(payload.home)

    async def run_turn(payload: TurnPayload) -> None:
        await engine.run(payload)

    return (
        TaskHandler(PURGE_DEPARTED, purge_departed),
        TaskHandler(SWEEP_LOST_RUNS, sweep_lost_runs),
        TaskHandler(RUN_TURN, run_turn),
    )
