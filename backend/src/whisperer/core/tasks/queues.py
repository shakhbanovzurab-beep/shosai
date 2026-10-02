"""Task queues: four latency classes, each a Valkey stream (target architecture §4.3, §12).

Queues are split by latency class, not by domain: a mass mailing must never delay a
sign-up confirmation (draft lesson). One worker process consumes one queue; every process
can enqueue to every queue. The stream keeps only unfinished tasks — a finished one is
acknowledged and deleted at once — so its length is the queue's depth.
"""

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from whisperer.core.kv.keys import build_key

CONSUMER_GROUP: Final = "whisperer"
# §4.3: поток не длиннее 500 000; полный поток отказывает в постановке, а не теряет старое.
STREAM_CAPACITY: Final = 500_000


class TaskQueue(StrEnum):
    """A latency class of background work; the value names its stream and metrics."""

    # Деньги и письма: человек ждёт результата прямо сейчас.
    CRITICAL = "critical"
    DEFAULT = "default"
    # Долгая пакетная работа: выгрузки, рассылки, пересчёты.
    BULK = "bulk"
    # Обработка встречи: долгая, но интерактивная, поэтому не в bulk.
    MEETING = "meeting"


@dataclass(frozen=True, slots=True)
class QueueProfile:
    """How many tasks of the queue one worker process runs at once."""

    concurrency: int


# Значения черновика, проверенные в production: без предела TaskIQ берёт сто задач при пуле
# базы в пять соединений; critical шире, потому что письма почти не держат соединение.
QUEUE_PROFILES: Final = MappingProxyType(
    {
        TaskQueue.CRITICAL: QueueProfile(concurrency=16),
        TaskQueue.DEFAULT: QueueProfile(concurrency=5),
        TaskQueue.BULK: QueueProfile(concurrency=3),
        TaskQueue.MEETING: QueueProfile(concurrency=3),
    }
)


def stream_key(queue: TaskQueue) -> str:
    """`whisperer:tasks:<queue>`: the stream of unfinished tasks of the queue."""
    return build_key("tasks", queue.value)


def dead_letter_key(queue: TaskQueue) -> str:
    """`whisperer:dead-letter:<queue>`: tasks of the queue that will not run again by themselves."""
    return build_key("dead-letter", queue.value)


def tick_key(task_name: str, *parts: str) -> str:
    """`whisperer:tick:<task>[:<part>…]`: the marker of a periodic task in flight."""
    return build_key("tick", task_name, *parts)
