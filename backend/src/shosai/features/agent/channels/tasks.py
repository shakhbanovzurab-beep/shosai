"""The slice's tasks (agent plan §3.1): Leo's turns, approved actions and the epilogues after
them on the `agent` queue, a thread's title and compaction after a turn, the minute's sweeps of
lost runs and of actions nobody decides or carries out, the hourly check of the actions'
invariants, the hourly purge of departed workspaces' threads and the daily purge of evaluation
cases past their year.

A turn is never retried by the queue (`application/turn_task.py`); the sweep and the purge are
per-home ticks that are not retried either — the next tick repeats them, and a pass takes at
most a batch.
"""

from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Final

from shosai.core.schedule.jobs import PeriodicJob
from shosai.core.tasks.declaration import NO_RETRY, TaskDeclaration, TaskHandler, TaskKind
from shosai.core.tasks.payloads import HomeTaskPayload
from shosai.core.tasks.queues import TaskQueue
from shosai.features.agent.application.action_decisions import RUN_ACTION, ActionPayload
from shosai.features.agent.application.action_execution import ActionExecution
from shosai.features.agent.application.action_invariants import ActionInvariants
from shosai.features.agent.application.action_sweeps import ActionSweeps
from shosai.features.agent.application.after_turn import COMPACT_THREAD, TITLE_THREAD, ThreadTask
from shosai.features.agent.application.case_care import CasePurge
from shosai.features.agent.application.departures import Departures
from shosai.features.agent.application.lost_runs import LostRuns
from shosai.features.agent.application.platform_images import PlatformImages
from shosai.features.agent.application.run_engine import RunEngine
from shosai.features.agent.application.run_resumption import RESUME_RUN, ResumePayload
from shosai.features.agent.application.thread_care import ThreadCare
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
SWEEP_ACTIONS: Final = tick("agent.sweep_actions", timedelta(seconds=50))
CHECK_ACTIONS: Final = tick("agent.check_actions", timedelta(minutes=5))
PURGE_CASES: Final = tick("agent.purge_cases", timedelta(minutes=5))
# Объекты картинок удалённых тредов оператора уходят из бакета (step 16b2).
RELEASE_IMAGES: Final = tick("agent.release_images", timedelta(minutes=5))
PERIODIC_JOBS: Final = (
    PeriodicJob(PURGE_DEPARTED, every=timedelta(hours=1)),
    PeriodicJob(SWEEP_LOST_RUNS, every=timedelta(minutes=1)),
    PeriodicJob(SWEEP_ACTIONS, every=timedelta(minutes=1)),
    PeriodicJob(CHECK_ACTIONS, every=timedelta(hours=1)),
    PeriodicJob(PURGE_CASES, every=timedelta(days=1)),
    PeriodicJob(RELEASE_IMAGES, every=timedelta(minutes=15)),
)


@dataclass(frozen=True, slots=True)
class Handlers:
    """What the slice's tasks call in this process."""

    departures: Departures
    lost_runs: LostRuns
    engine: RunEngine
    care: ThreadCare
    actions: tuple[ActionExecution, ActionSweeps, ActionInvariants]
    # Чистки: случаи оценки и объекты картинок оператора.
    purges: tuple[CasePurge, PlatformImages]


def task_handlers(handlers: Handlers) -> tuple[TaskHandler[Any], ...]:
    """The handlers of the slice's tasks in this process."""
    return (*agent_queue_handlers(handlers), *upkeep_handlers(handlers))


def agent_queue_handlers(handlers: Handlers) -> tuple[TaskHandler[Any], ...]:
    """The `agent` queue's tasks: turns, approved actions and the epilogues after them."""
    engine, (execution, _, _) = handlers.engine, handlers.actions

    async def run_turn(payload: TurnPayload) -> None:
        await engine.run(payload)

    async def run_action(payload: ActionPayload) -> None:
        if payload.user_id is None:
            message = "действие Leo исполняется от имени человека"
            raise ValueError(message)
        await execution.run(payload.home, payload.user_id, payload.action_id)

    async def resume_run(payload: ResumePayload) -> None:
        await engine.resume(payload)

    return (
        TaskHandler(RUN_TURN, run_turn),
        TaskHandler(RUN_ACTION, run_action),
        TaskHandler(RESUME_RUN, resume_run),
    )


def upkeep_handlers(handlers: Handlers) -> tuple[TaskHandler[Any], ...]:
    """The work around turns: titles and compaction, the sweeps, the check and the purges."""
    departures, lost_runs, care = handlers.departures, handlers.lost_runs, handlers.care
    _, sweeps, invariants = handlers.actions

    async def title_thread(payload: ThreadTask) -> None:
        await care.title(payload)

    async def compact_thread(payload: ThreadTask) -> None:
        await care.compact(payload)

    async def purge_departed(payload: HomeTaskPayload) -> None:
        await departures.purge(payload.home)

    async def sweep_lost_runs(payload: HomeTaskPayload) -> None:
        await lost_runs.sweep(payload.home)

    async def sweep_actions(payload: HomeTaskPayload) -> None:
        await sweeps.sweep(payload.home)

    async def check_actions(payload: HomeTaskPayload) -> None:
        await invariants.check(payload.home)

    async def purge_cases(payload: HomeTaskPayload) -> None:
        await handlers.purges[0].purge(payload.home)

    async def release_images(payload: HomeTaskPayload) -> None:
        await handlers.purges[1].release(payload.home)

    return (
        TaskHandler(PURGE_DEPARTED, purge_departed),
        TaskHandler(SWEEP_LOST_RUNS, sweep_lost_runs),
        TaskHandler(SWEEP_ACTIONS, sweep_actions),
        TaskHandler(CHECK_ACTIONS, check_actions),
        TaskHandler(PURGE_CASES, purge_cases),
        TaskHandler(RELEASE_IMAGES, release_images),
        TaskHandler(TITLE_THREAD, title_thread),
        TaskHandler(COMPACT_THREAD, compact_thread),
    )
