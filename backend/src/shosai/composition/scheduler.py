"""The loops of core in the scheduler: outbox relay and purges per home, queue and outbox gauges.

The relay of each home is queued every 5 s (§12: a tick drains the due events), the purges
of the outbox and of the effect keys once a day; each is a tick, skipped while the previous
one of its home runs (`send_tick`), so a slow or unreachable home never piles up work or
delays the other. The gauges are set by
this one process: depth and age are properties of a queue and of a home, not of a worker.
"""

from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Final

from shosai.composition.platform import Platform
from shosai.core.events.monitor import OutboxMonitor
from shosai.core.events.system import PURGE_EVERY, PURGE_OUTBOX, RELAY_EVERY, RELAY_OUTBOX
from shosai.core.idempotency.system import PURGE_EFFECT_KEYS, PURGE_KEYS_EVERY
from shosai.core.kernel.homes import Home
from shosai.core.runtime.loops import ScheduledLoop
from shosai.core.tasks.declaration import TaskDeclaration
from shosai.core.tasks.monitor import QueueMonitor
from shosai.core.tasks.payloads import HomeTaskPayload
from shosai.core.tasks.sender import TaskSender

# Как часто Prometheus опрашивает процессы: замер чаще ничего не добавит.
MONITOR_EVERY: Final = timedelta(seconds=15)


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
            ScheduledLoop(
                f"events.purge_outbox.{home.value}",
                PURGE_EVERY,
                home_tick(sender, PURGE_OUTBOX, home),
            )
            for home in Home
        ),
        *(
            ScheduledLoop(
                f"idempotency.purge_keys.{home.value}",
                PURGE_KEYS_EVERY,
                home_tick(sender, PURGE_EFFECT_KEYS, home),
            )
            for home in Home
        ),
        ScheduledLoop("tasks.queue_monitor", MONITOR_EVERY, queues.refresh),
        ScheduledLoop("events.outbox_monitor", MONITOR_EVERY, outbox.refresh),
    )
