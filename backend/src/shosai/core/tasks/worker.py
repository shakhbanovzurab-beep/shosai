"""Consuming one queue in a worker process with TaskIQ's receiver (target architecture §5).

The receiver runs at most the queue's concurrency at once and asks the broker for the
next message only when a run slot is free. When `stop` is set it takes no new messages
and waits for the running ones up to the queue's drain time, which is shorter than the stop
grace period of its container; what is still running then returns to the queue after the
lease, and another worker runs it again or, for a task that is never retried, settles it.
"""

import asyncio
from datetime import timedelta

from taskiq.acks import AcknowledgeType
from taskiq.receiver import Receiver

from shosai.core.tasks.broker import ValkeyStreamBroker
from shosai.core.tasks.queues import QUEUE_PROFILES


async def consume_queue(
    broker: ValkeyStreamBroker, stop: asyncio.Event, *, drain: timedelta | None = None
) -> None:
    """Run the tasks of the broker's queue until `stop` is set, then drain."""
    profile = QUEUE_PROFILES[broker.queue]
    broker.is_worker_process = True
    receiver = Receiver(
        broker=broker,
        executor=None,
        # Разбор параметров приёмника пишет отклонённый ввод в лог; данные задачи проверяет
        # функция задачи (core/tasks/handlers.py).
        validate_params=False,
        max_async_tasks=profile.concurrency,
        max_prefetch=0,
        run_startup=False,
        # Подтверждение после post_execute: к этому моменту жизненный цикл решил, что делать
        # с сообщением. WHEN_EXECUTED подтверждал бы раньше решения.
        ack_type=AcknowledgeType.WHEN_SAVED,
        wait_tasks_timeout=(profile.drain if drain is None else drain).total_seconds(),
    )
    await broker.startup()
    try:
        await receiver.listen(stop)
    finally:
        await broker.shutdown()
