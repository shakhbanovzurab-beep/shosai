"""The task system of one process: a broker per queue with every task, and the sender.

Every role registers every task (draft lesson: a worker built without a slice's tasks
dropped them as unknown). The sender exists before any handler, because a handler may
queue further work — a pipeline stage queues the next one, the outbox relay queues
deliveries — and slices receive it together with the other core services. Composition
then registers the handlers of every slice before the role starts. Each handler goes to
the broker of its queue, and a name may be declared only once in the whole backend.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from opentelemetry.sdk.trace import TracerProvider
from prometheus_client import CollectorRegistry
from redis.asyncio import Redis

from shosai.core.tasks.broker import ValkeyStreamBroker, new_consumer_name
from shosai.core.tasks.declaration import TaskDeclaration, TaskHandler
from shosai.core.tasks.lifecycle import TaskLifecycle
from shosai.core.tasks.metrics import TaskMetrics
from shosai.core.tasks.queues import STREAM_CAPACITY, TaskQueue
from shosai.core.tasks.sender import TaskSender
from shosai.core.tasks.stream import TaskStream
from shosai.core.tasks.ticks import TickMarkers
from shosai.core.tasks.timing import StreamTiming
from shosai.core.tasks.tracing import TaskTracing


@dataclass(frozen=True, slots=True)
class TaskSystem:
    """The brokers of every queue, the sender slices receive, and the task metrics."""

    brokers: Mapping[TaskQueue, ValkeyStreamBroker]
    sender: TaskSender
    metrics: TaskMetrics

    def register(self, handlers: Sequence[TaskHandler[Any]]) -> None:
        """Make every handler runnable on the broker of its queue; a name only once."""
        for handler in handlers:
            name = handler.task.name
            if any(broker.declaration(name) is not None for broker in self.brokers.values()):
                message = f"задача {name} объявлена дважды"
                raise ValueError(message)
            self.brokers[handler.task.queue].register(handler)

    def declares(self, task: TaskDeclaration[Any]) -> bool:
        """Whether this process registered the task on the broker of its queue."""
        return self.brokers[task.queue].declaration(task.name) is not None


@dataclass(frozen=True, slots=True)
class StreamOptions:
    """What differs from production in tests: time limits, the consumer, the stream bound."""

    timing: StreamTiming = field(default_factory=StreamTiming)
    consumer: str | None = None
    capacity: int = STREAM_CAPACITY


def build_task_system(
    client: Redis,
    registry: CollectorRegistry,
    tracer_provider: TracerProvider,
    options: StreamOptions | None = None,
) -> TaskSystem:
    """The brokers and the sender over the process's Valkey client, before any handler."""
    chosen = options or StreamOptions()
    consumer = chosen.consumer or new_consumer_name()
    metrics = TaskMetrics(registry)
    ticks = TickMarkers(client)
    brokers: dict[TaskQueue, ValkeyStreamBroker] = {}
    for queue in TaskQueue:
        stream = TaskStream(client, queue, chosen.timing, consumer, capacity=chosen.capacity)
        broker = ValkeyStreamBroker(stream, metrics)
        # Трассировка снаружи: строки жизненного цикла пишутся внутри спана выполнения.
        broker.add_middlewares(
            TaskTracing(tracer_provider, queue), TaskLifecycle(broker, metrics, ticks)
        )
        brokers[queue] = broker
    frozen = MappingProxyType(brokers)
    return TaskSystem(brokers=frozen, sender=TaskSender(frozen, ticks, metrics), metrics=metrics)
