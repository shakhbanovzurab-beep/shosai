"""What a slice or core declares to run on time: a periodic job or a due-row source (§12).

A **periodic job** runs once per interval in each of its homes, however many scheduler
processes run and however often they restart: its last run is a row of `schedule_runs` in
the home, claimed by one conditional update (F6-C13). A missed interval runs once, never as
a backlog, and a deploy does not run a daily job again (draft lesson: "daily" sub-jobs ran
on every deploy).

A **due-row source** is a slice's table of rows that fall due (errands, proactive
triggers): the scheduler queues the slice's sweep task every few seconds per home, and the
sweep claims its due rows with `claim_due` (F6-C14). Both queue tick tasks, so a slow run is
never stacked under the next one.
"""

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Final

from shosai.core.kernel.homes import Home
from shosai.core.tasks.declaration import TaskDeclaration, TaskKind
from shosai.core.tasks.payloads import HomeTaskPayload

# Чаще раза в минуту — это источник строк к сроку или цикл, а не запись в schedule_runs.
SHORTEST_JOB_INTERVAL: Final = timedelta(minutes=1)
SHORTEST_SWEEP_INTERVAL: Final = timedelta(seconds=1)
EVERY_HOME: Final = tuple(Home)


def _check_tick(task: TaskDeclaration[HomeTaskPayload], homes: tuple[Home, ...]) -> None:
    if task.kind is not TaskKind.TICK or task.payload is not HomeTaskPayload:
        message = f"задача {task.name}: по расписанию ставится такт с HomeTaskPayload"
        raise ValueError(message)
    if not homes or len(set(homes)) != len(homes):
        message = f"задача {task.name}: дома перечислены без повторов, хотя бы один"
        raise ValueError(message)


@dataclass(frozen=True, slots=True)
class PeriodicJob:
    """A tick task queued once per interval in each of its homes; its name is the task's."""

    task: TaskDeclaration[HomeTaskPayload]
    every: timedelta
    homes: tuple[Home, ...] = field(default=EVERY_HOME)

    def __post_init__(self) -> None:
        _check_tick(self.task, self.homes)
        if self.every < SHORTEST_JOB_INTERVAL:
            message = f"задача {self.task.name}: период не короче минуты"
            raise ValueError(message)

    @property
    def name(self) -> str:
        """The job's key in `schedule_runs`."""
        return self.task.name


@dataclass(frozen=True, slots=True)
class DueRowSource:
    """A slice's sweep task, queued every few seconds per home to claim its due rows."""

    sweep: TaskDeclaration[HomeTaskPayload]
    every: timedelta
    homes: tuple[Home, ...] = field(default=EVERY_HOME)

    def __post_init__(self) -> None:
        _check_tick(self.sweep, self.homes)
        if self.every < SHORTEST_SWEEP_INTERVAL:
            message = f"обход {self.sweep.name}: период не короче секунды"
            raise ValueError(message)

    @property
    def name(self) -> str:
        """The source's name: its sweep task's."""
        return self.sweep.name
