"""Queue gauges read from Valkey: depth, age of the oldest task, dead-letter entries (§16.4).

Depth is a property of the queue, not of a worker, so one process — the scheduler — sets
the gauges; summing a value published by every worker would mean nothing (draft lesson).
The stream holds only unfinished tasks, so its length is the depth and its first entry
the oldest task. The dead letter is alerted on its newest entry, not on its size: entries
live a week, and an alert on size would keep firing long after the cause was fixed.
"""

import asyncio
import time
from collections.abc import Callable, Sequence
from typing import Final

from redis.asyncio import Redis

from shosai.core.kv.connection import REDIS_FAILURES
from shosai.core.observability.outage_log import OutageLog
from shosai.core.tasks import scripts
from shosai.core.tasks.metrics import TaskMetrics
from shosai.core.tasks.queues import TaskQueue, dead_letter_key, stream_key
from shosai.core.tasks.stream import WORKER_CALL_DEADLINE, as_text

# Ответ скрипта на очередь: длина, первая запись, длина dead letter, его последняя запись.
VALUES_PER_QUEUE: Final = 4


def count_of(value: object) -> int:
    """An integer reply of Valkey."""
    return value if isinstance(value, int) else int(as_text(value))


def id_time(stream_id: object) -> float | None:
    """Unix time of a stream entry id, or None when there is no entry."""
    if stream_id is None:
        return None
    return int(as_text(stream_id).partition("-")[0]) / 1000


class QueueMonitor:
    """Refreshes the queue gauges of every queue in one round trip."""

    def __init__(
        self, client: Redis, metrics: TaskMetrics, clock: Callable[[], float] = time.time
    ) -> None:
        self._metrics = metrics
        self._gauges = metrics.gauges
        self._clock = clock
        self._read_gauges = client.register_script(scripts.QUEUE_GAUGES)
        self._outages = OutageLog("Valkey не ответил замеру очередей")

    async def refresh(self) -> bool:
        """Read every queue and set its gauges; False when Valkey did not answer in time."""
        keys = [key for queue in TaskQueue for key in (stream_key(queue), dead_letter_key(queue))]
        try:
            async with asyncio.timeout(WORKER_CALL_DEADLINE.total_seconds()):
                values: Sequence[object] = await self._read_gauges(keys=keys)
        except REDIS_FAILURES as error:
            for queue in TaskQueue:
                self._metrics.count_valkey_failure(queue, "monitor")
            self._outages.failed(error, operation="monitor")
            return False
        now = self._clock()
        for index, queue in enumerate(TaskQueue):
            depth, oldest, dead, newest = values[
                index * VALUES_PER_QUEUE : (index + 1) * VALUES_PER_QUEUE
            ]
            oldest_at = id_time(oldest)
            label = queue.value
            self._gauges.depth.labels(queue=label).set(count_of(depth))
            self._gauges.oldest_age.labels(queue=label).set(
                0.0 if oldest_at is None else max(now - oldest_at, 0.0)
            )
            self._gauges.dead_letter_entries.labels(queue=label).set(count_of(dead))
            self._gauges.dead_letter_newest.labels(queue=label).set(id_time(newest) or 0.0)
        return True
