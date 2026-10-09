"""The event tasks of a process: the relay and the purge of each home, and every delivery.

Every role registers them all, like every other task (§14 rule 9). The scheduler queues
a relay tick per home every 5 seconds (§12: up to 100 events per 5 s) and a purge tick
per home once a day; a tick is skipped while the previous one of its home runs. Each
home has its own tick marker, so a slow or unreachable home never delays the other.
"""

from datetime import timedelta
from typing import Any, Final

from shosai.core.events.delivery import delivery_handler
from shosai.core.events.purge import OutboxPurge
from shosai.core.events.relay import DeliverySender, OutboxRelay
from shosai.core.events.resources import EventResources
from shosai.core.tasks.declaration import NO_RETRY, TaskDeclaration, TaskHandler, TaskKind
from shosai.core.tasks.payloads import HomeTaskPayload
from shosai.core.tasks.queues import TaskQueue

RELAY_EVERY: Final = timedelta(seconds=5)
PURGE_EVERY: Final = timedelta(days=1)

# В critical: события несут письма и деньги, им не место за часовой выгрузкой. Дедлайн
# короче аренды захвата (30 с), чтобы соседний проход не взял строки идущего.
RELAY_OUTBOX: Final = TaskDeclaration(
    name="events.relay_outbox",
    queue=TaskQueue.CRITICAL,
    payload=HomeTaskPayload,
    deadline=timedelta(seconds=25),
    retry=NO_RETRY,
    kind=TaskKind.TICK,
)
PURGE_OUTBOX: Final = TaskDeclaration(
    name="events.purge_outbox",
    queue=TaskQueue.BULK,
    payload=HomeTaskPayload,
    deadline=timedelta(minutes=10),
    retry=NO_RETRY,
    kind=TaskKind.TICK,
)


def event_task_handlers(
    resources: EventResources, sender: DeliverySender
) -> list[TaskHandler[Any]]:
    """The relay, the purge and one delivery task per subscription, bound to the process."""
    relay = OutboxRelay(resources, sender)
    purge = OutboxPurge(resources.transactions, resources.metrics, resources.retention)

    async def relay_outbox(payload: HomeTaskPayload) -> None:
        await relay.relay(payload.home)

    async def purge_outbox(payload: HomeTaskPayload) -> None:
        await purge.purge(payload.home)

    return [
        TaskHandler(RELAY_OUTBOX, relay_outbox),
        TaskHandler(PURGE_OUTBOX, purge_outbox),
        *(
            delivery_handler(
                route.subscription, route.task, resources.transactions, resources.metrics
            )
            for route in resources.catalog.all_routes()
        ),
    ]
