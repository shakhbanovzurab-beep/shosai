"""Applying the settlement of a delivery in Valkey, and the failures of queue operations.

When Valkey does not answer, nothing is lost: a message that was not acknowledged, sent
back or moved stays in the consumer's pending list and returns after the lease. The run
may then repeat, which every task must tolerate (at-least-once delivery).
"""

from datetime import timedelta

import structlog

from whisperer.core.kv.connection import REDIS_FAILURES
from whisperer.core.observability.outage_log import OutageLog
from whisperer.core.tasks.dead_letter import DeadLetterEntry
from whisperer.core.tasks.deliveries import (
    Acknowledge,
    Delivery,
    LeavePending,
    MoveToDeadLetter,
    RetryLater,
)
from whisperer.core.tasks.metrics import TaskMetrics, ValkeyOperation
from whisperer.core.tasks.stream import TaskStream

log = structlog.stdlib.get_logger(__name__)


class QueueFailures:
    """Counts every Valkey failure of a queue's operations and logs them at most once per 10 s."""

    def __init__(self, stream: TaskStream, metrics: TaskMetrics) -> None:
        self._queue = stream.queue
        self._metrics = metrics
        self._outages = OutageLog("Valkey не ответил очереди задач")

    def record(self, operation: ValkeyOperation, error: BaseException) -> None:
        """One failed operation."""
        self._metrics.count_valkey_failure(self._queue, operation)
        self._outages.failed(error, queue=self._queue.value, operation=operation)


class DeliverySettler:
    """Acknowledges, retries later or dead-letters the messages of one queue."""

    def __init__(self, stream: TaskStream, metrics: TaskMetrics, failures: QueueFailures) -> None:
        self._stream = stream
        self._queue = stream.queue
        self._metrics = metrics
        self._failures = failures

    async def settle(self, delivery: Delivery) -> None:
        """Apply the settlement decided when the delivery's run ended."""
        match delivery.settlement:
            case Acknowledge():
                # Удачный прогон закрывает сообщение, даже если аренду уже забрал сосед.
                await self.acknowledge(delivery.stream_id)
            case RetryLater(delay=delay):
                await self.retry_later(delivery, delay)
            case MoveToDeadLetter(entry=record):
                await self.dead_letter(delivery.stream_id, record)
            case LeavePending():
                return
            case None:
                log.error(
                    "Выдача завершилась без решения: сообщение вернётся после аренды",
                    queue=self._queue.value,
                    task_name=delivery.task.name,
                    task_id=delivery.task_id,
                )

    async def acknowledge(self, stream_id: str) -> None:
        """Remove a message from the queue."""
        try:
            await self._stream.acknowledge(stream_id)
        except REDIS_FAILURES as error:
            # Сообщение останется в ожидании и выполнится ещё раз после аренды.
            self._failures.record("acknowledge", error)

    async def retry_later(self, delivery: Delivery, delay: timedelta) -> None:
        """Send a message back to the queue for a delivery after `delay`."""
        try:
            kept = await self._stream.retry_later(delivery.stream_id, delay)
        except REDIS_FAILURES as error:
            # Без отложенного повтора сообщение вернётся после аренды — позже, но не потеряется.
            self._failures.record("retry", error)
            return
        if not kept:
            log.warning(
                "Повтор не назначен: сообщение уже у другого воркера",
                queue=self._queue.value,
                task_name=delivery.task.name,
                task_id=delivery.task_id,
            )

    async def dead_letter(self, stream_id: str, record: DeadLetterEntry) -> None:
        """Move a message to the queue's dead letter."""
        try:
            moved = await self._stream.dead_letter(stream_id, record.encode())
        except REDIS_FAILURES as error:
            # Сообщение останется в ожидании и придёт сюда снова после аренды.
            self._failures.record("dead_letter", error)
            return
        if moved:
            self._metrics.count_dead_letter(self._queue, record.reason)
