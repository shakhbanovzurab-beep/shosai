"""The task system of one process: a broker per queue with every task, and the sender.

Every role registers every task (draft lesson: a worker built without a slice's tasks
dropped them as unknown). Composition passes the handlers of all slices; each goes to the
broker of its queue, and a name may be declared only once in the whole backend.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from opentelemetry.sdk.trace import TracerProvider
from prometheus_client import CollectorRegistry
from redis.asyncio import Redis

from whisperer.core.tasks.broker import ValkeyStreamBroker, new_consumer_name
from whisperer.core.tasks.declaration import TaskHandler
from whisperer.core.tasks.lifecycle import TaskLifecycle
from whisperer.core.tasks.metrics import TaskMetrics
from whisperer.core.tasks.queues import STREAM_CAPACITY, TaskQueue
from whisperer.core.tasks.sender import TaskSender
from whisperer.core.tasks.stream import TaskStream
from whisperer.core.tasks.ticks import TickMarkers
from whisperer.core.tasks.timing import StreamTiming
from whisperer.core.tasks.tracing import TaskTracing


@dataclass(frozen=True, slots=True)
class TaskSystem:
    """The brokers of every queue, the sender slices receive, and the task metrics."""

    brokers: Mapping[TaskQueue, ValkeyStreamBroker]
    sender: TaskSender
    metrics: TaskMetrics


@dataclass(frozen=True, slots=True)
class StreamOptions:
    """What differs from production in tests: time limits, the consumer, the stream bound."""

    timing: StreamTiming = field(default_factory=StreamTiming)
    consumer: str | None = None
    capacity: int = STREAM_CAPACITY


def build_task_system(
    client: Redis,
    handlers: Sequence[TaskHandler[Any]],
    registry: CollectorRegistry,
    tracer_provider: TracerProvider,
    options: StreamOptions | None = None,
) -> TaskSystem:
    """The task system over the process's Valkey client, with every handler registered."""
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
    seen: set[str] = set()
    for handler in handlers:
        if handler.task.name in seen:
            message = f"задача {handler.task.name} объявлена дважды"
            raise ValueError(message)
        seen.add(handler.task.name)
        brokers[handler.task.queue].register(handler)
    frozen = MappingProxyType(brokers)
    return TaskSystem(brokers=frozen, sender=TaskSender(frozen, ticks, metrics), metrics=metrics)
