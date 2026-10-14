"""The loops of core in the scheduler: relay and job walk per home, due-row sources, gauges.

The relay of each home is queued every 5 s (§12: a tick drains the due events). The walk of
each home claims and queues the due periodic jobs — core's daily purges and upkeep and every
slice's jobs — once per interval whatever the restarts (F6 step 1). Each due-row source of
a slice is queued every few seconds per home. Every queued task is a tick, skipped while
the previous one of its home runs (`send_tick`), so a slow or unreachable home never piles
up work or delays the other. The gauges are set by this one process: depth and age are
properties of a queue and of a home, not of a worker.
"""

from collections.abc import Awaitable, Callable
from datetime import timedelta
from functools import partial
from typing import Final

from shosai.composition.platform import Platform
from shosai.core.email.system import EMAIL_SWEEP_SOURCE
from shosai.core.events.monitor import OutboxMonitor
from shosai.core.events.system import RELAY_EVERY, RELAY_OUTBOX
from shosai.core.kernel.homes import Home
from shosai.core.runtime.loops import ScheduledLoop
from shosai.core.schedule.metrics import ScheduleMetrics
from shosai.core.schedule.walker import ScheduleWalker
from shosai.core.tasks.declaration import TaskDeclaration
from shosai.core.tasks.monitor import QueueMonitor
from shosai.core.tasks.payloads import HomeTaskPayload
from shosai.core.tasks.sender import TaskSender

# Как часто Prometheus опрашивает процессы: замер чаще ничего не добавит.
MONITOR_EVERY: Final = timedelta(seconds=15)
# Обход периодических задач: задача с периодом от минуты опоздает не больше чем на 5 с.
WALK_EVERY: Final = timedelta(seconds=5)


def home_tick(
    sender: TaskSender, task: TaskDeclaration[HomeTaskPayload], home: Home
) -> Callable[[], Awaitable[bool]]:
    """Queue the task's tick for one home, with the home as its marker."""

    async def tick() -> bool:
        return await sender.send_tick(task, HomeTaskPayload(home=home), home.value)

    return tick


def core_loops(platform: Platform) -> tuple[ScheduledLoop, ...]:
    """The loops every scheduler runs, whatever slices it has."""
    sender = platform.tasks.sender
    queues = QueueMonitor(platform.services.valkey, platform.tasks.metrics)
    outbox = OutboxMonitor(platform.events.transactions, platform.events.metrics)
    walker = ScheduleWalker(
        platform.events.transactions,
        sender,
        ScheduleMetrics(platform.services.registry),
        platform.jobs,
    )
    return (
        *(
            ScheduledLoop(
                f"events.relay_outbox.{home.value}",
                RELAY_EVERY,
                home_tick(sender, RELAY_OUTBOX, home),
            )
            for home in Home
        ),
        *(
            ScheduledLoop(f"schedule.walk.{home.value}", WALK_EVERY, partial(walker.walk, home))
            for home in Home
        ),
        *(
            ScheduledLoop(
                f"{source.name}.{home.value}", source.every, home_tick(sender, source.sweep, home)
            )
            for source in (EMAIL_SWEEP_SOURCE, *platform.parts.due_sources)
            for home in source.homes
        ),
        ScheduledLoop("tasks.queue_monitor", MONITOR_EVERY, queues.refresh),
        ScheduledLoop("events.outbox_monitor", MONITOR_EVERY, outbox.refresh),
    )
