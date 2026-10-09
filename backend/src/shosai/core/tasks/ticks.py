"""Tick markers: a periodic task is not queued again while its previous tick is in flight.

The scheduler sets the marker when it queues a tick, and the worker removes it when the
tick's run ends, whatever the outcome. While the marker exists the next tick is skipped,
so slow ticks during an outage never pile up and exhaust the database pool (draft
lesson: 176 overlapping relay ticks). A marker holds the tick's task id and is removed
only by that tick; if the worker dies, the marker expires with the task's hold limit.
"""

import asyncio
from datetime import timedelta
from typing import Final

from redis.asyncio import Redis

from shosai.core.kv.connection import REDIS_FAILURES
from shosai.core.kv.locks import RELEASE_SCRIPT, lock_milliseconds
from shosai.core.observability.outage_log import OutageLog

# §4.3: такт планировщика ждёт Valkey не дольше 50 мс; повтор — следующий такт.
TICK_DEADLINE: Final = timedelta(milliseconds=50)


class TickMarkers:
    """Sets and removes the markers of periodic tasks in flight."""

    def __init__(self, client: Redis) -> None:
        self._client = client
        self._release = client.register_script(RELEASE_SCRIPT)
        self._outages = OutageLog("Valkey не ответил: маркер такта снимется по сроку")

    async def mark(self, key: str, task_id: str, ttl: timedelta) -> bool:
        """Set the marker of a tick about to be queued; False while the previous one runs."""
        async with asyncio.timeout(TICK_DEADLINE.total_seconds()):
            marked = await self._client.set(key, task_id, nx=True, px=lock_milliseconds(ttl))
        return marked is True

    async def release(self, key: str, task_id: str) -> None:
        """Remove the marker if it is still this tick's; when Valkey is out, it expires instead."""
        try:
            async with asyncio.timeout(TICK_DEADLINE.total_seconds()):
                await self._release(keys=[key], args=[task_id])
        except REDIS_FAILURES as error:
            self._outages.failed(error, operation="release")
