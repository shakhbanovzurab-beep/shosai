"""Consuming one queue in a worker process with TaskIQ's receiver (target architecture §5).

The receiver runs at most the queue's concurrency at once and asks the broker for the
next message only when a run slot is free. When `stop` is set it takes no new messages
and waits for the running ones up to the drain time; what is still running then returns
to the queue after the lease, and another worker runs it again.
"""

import asyncio
from datetime import timedelta
from typing import Final

from taskiq.acks import AcknowledgeType
from taskiq.receiver import Receiver

from whisperer.core.tasks.broker import ValkeyStreamBroker
from whisperer.core.tasks.queues import QUEUE_PROFILES

# Ожидание начатых задач при остановке: меньше отсрочки до SIGKILL у контейнера (шаг 8).
DRAIN_TIMEOUT: Final = timedelta(seconds=20)


async def consume_queue(
    broker: ValkeyStreamBroker, stop: asyncio.Event, *, drain: timedelta = DRAIN_TIMEOUT
) -> None:
    """Run the tasks of the broker's queue until `stop` is set, then drain."""
    broker.is_worker_process = True
    receiver = Receiver(
        broker=broker,
        executor=None,
        # Разбор параметров приёмника пишет отклонённый ввод в лог; данные задачи проверяет
        # функция задачи (core/tasks/handlers.py).
        validate_params=False,
        max_async_tasks=QUEUE_PROFILES[broker.queue].concurrency,
        max_prefetch=0,
        run_startup=False,
        # Подтверждение после post_execute: к этому моменту жизненный цикл решил, что делать
        # с сообщением. WHEN_EXECUTED подтверждал бы раньше решения.
        ack_type=AcknowledgeType.WHEN_SAVED,
        wait_tasks_timeout=drain.total_seconds(),
    )
    await broker.startup()
    try:
        await receiver.listen(stop)
    finally:
        await broker.shutdown()
