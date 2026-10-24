"""Task queues: five latency classes, each a Valkey stream (target architecture §4.3, §12).

Queues are split by latency class, not by domain: a mass mailing must never delay a
sign-up confirmation (draft lesson). One worker process consumes one queue; every process
can enqueue to every queue. The stream keeps only unfinished tasks — a finished one is
acknowledged and deleted at once — so its length is the queue's depth. Leo's turns have a
queue of their own (ADR 0068 AG-D12): many long, mostly waiting runs per process, drained
for up to 190 s on a release, while every other worker drains for 20 s.
"""

from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from shosai.core.kv.keys import build_key

CONSUMER_GROUP: Final = "shosai"
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
    # Ходы Leo: человек ждёт поток ответа, ход почти всё время ждёт модель (AG-D12).
    AGENT = "agent"


# Ожидание начатых задач при остановке и отсрочка SIGKILL у контейнера (stop_grace_period).
DRAIN: Final = timedelta(seconds=20)
STOP_GRACE: Final = timedelta(seconds=30)


@dataclass(frozen=True, slots=True)
class QueueProfile:
    """How many tasks of the queue one worker process runs at once, how long it waits for
    them on a stop, and the stop grace period its container is given for that."""

    concurrency: int
    drain: timedelta = DRAIN
    stop_grace: timedelta = STOP_GRACE


# Значения черновика, проверенные в production: без предела TaskIQ берёт сто задач при пуле
# базы в пять соединений; critical шире, потому что письма почти не держат соединение. Ход Leo
# держит соединение с базой только в своих двух транзакциях и ждёт модель до 180 с, поэтому
# воркер ходов ведёт 48 ходов и при выкатке дослушивает их до конца (AG-D12).
QUEUE_PROFILES: Final = MappingProxyType(
    {
        TaskQueue.CRITICAL: QueueProfile(concurrency=16),
        TaskQueue.DEFAULT: QueueProfile(concurrency=5),
        TaskQueue.BULK: QueueProfile(concurrency=3),
        TaskQueue.MEETING: QueueProfile(concurrency=3),
        TaskQueue.AGENT: QueueProfile(
            concurrency=48, drain=timedelta(seconds=190), stop_grace=timedelta(seconds=200)
        ),
    }
)


def stream_key(queue: TaskQueue) -> str:
    """`shosai:tasks:<queue>`: the stream of unfinished tasks of the queue."""
    return build_key("tasks", queue.value)


def dead_letter_key(queue: TaskQueue) -> str:
    """`shosai:dead-letter:<queue>`: tasks of the queue that will not run again by themselves."""
    return build_key("dead-letter", queue.value)


def tick_key(task_name: str, *parts: str) -> str:
    """`shosai:tick:<task>[:<part>…]`: the marker of a periodic task in flight."""
    return build_key("tick", task_name, *parts)
