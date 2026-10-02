"""The task system of one process: a broker per queue with every task, and the sender.

Every role registers every task (draft lesson: a worker built without a slice's tasks
dropped them as unknown). Composition passes a binding that builds the handlers of all
slices with the process's sender, because a handler may queue further work: a pipeline
stage queues the next one, the outbox relay queues deliveries. Each handler goes to the
broker of its queue, and a name may be declared only once in the whole backend.
"""

from collections.abc import Callable, Mapping, Sequence
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


# Обработчики строятся с отправителем процесса: обработчик может ставить задачи сам.
type HandlerBinding = Callable[[TaskSender], Sequence[TaskHandler[Any]]]


def build_task_system(
    client: Redis,
    bind_handlers: HandlerBinding,
    registry: CollectorRegistry,
    tracer_provider: TracerProvider,
    options: StreamOptions | None = None,
) -> TaskSystem:
    """The task system over the process's Valkey client, with every bound handler registered."""
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
    sender = TaskSender(frozen, ticks, metrics)
    seen: set[str] = set()
    for handler in bind_handlers(sender):
        if handler.task.name in seen:
            message = f"задача {handler.task.name} объявлена дважды"
            raise ValueError(message)
        seen.add(handler.task.name)
        brokers[handler.task.queue].register(handler)
    return TaskSystem(brokers=frozen, sender=sender, metrics=metrics)
