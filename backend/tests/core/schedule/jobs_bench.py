"""Probe periodic jobs and a sender that records ticks or fails them as planned."""

from dataclasses import dataclass, field
from datetime import timedelta

from shosai.core.kernel.homes import Home
from shosai.core.schedule.jobs import PeriodicJob
from shosai.core.tasks.declaration import NO_RETRY, TaskDeclaration, TaskKind
from shosai.core.tasks.errors import TaskQueueUnavailableError
from shosai.core.tasks.payloads import HomeTaskPayload, TaskPayload
from shosai.core.tasks.queues import TaskQueue


def tick(name: str) -> TaskDeclaration[HomeTaskPayload]:
    """A probe tick task."""
    return TaskDeclaration(
        name=name,
        queue=TaskQueue.BULK,
        payload=HomeTaskPayload,
        deadline=timedelta(minutes=1),
        retry=NO_RETRY,
        kind=TaskKind.TICK,
    )


HOURLY = PeriodicJob(tick("probe.hourly_digest"), timedelta(hours=1))
DAILY_EU = PeriodicJob(tick("probe.daily_report"), timedelta(days=1), homes=(Home.EU,))


@dataclass
class RecordingTicks:
    """Records each queued tick; jobs in `failing` raise, jobs in `in_flight` are skipped."""

    failing: set[str] = field(default_factory=set)
    in_flight: set[str] = field(default_factory=set)
    sent: list[tuple[str, str]] = field(default_factory=list)

    async def send_tick[P: TaskPayload](
        self, task: TaskDeclaration[P], payload: P, *marker: str
    ) -> bool:
        """Record the tick, or fail or skip it as planned."""
        if task.name in self.failing:
            raise TaskQueueUnavailableError(task.queue)
        if task.name in self.in_flight:
            return False
        if not isinstance(payload, HomeTaskPayload) or marker != (payload.home.value,):
            message = "такт расписания несёт дом и метку дома"
            raise TypeError(message)
        self.sent.append((task.name, payload.home.value))
        return True
