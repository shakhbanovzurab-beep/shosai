"""Valkey operations on the stream of one queue (ADR 0016); every call has a deadline.

The stream holds only unfinished tasks. One consumer group reads it from the first entry,
so tasks queued before the group existed are not skipped (draft lesson). A message stays in
its consumer's pending list until it is acknowledged (and deleted), sent back for a later
retry, or moved to the dead letter; a message idle longer than the lease is claimed again
by any worker of the queue, and each claim counts one more delivery.
"""

import asyncio
import time
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import timedelta
from typing import Final

from redis.asyncio import Redis
from redis.exceptions import ResponseError

from whisperer.core.tasks import scripts
from whisperer.core.tasks.queues import (
    CONSUMER_GROUP,
    STREAM_CAPACITY,
    TaskQueue,
    dead_letter_key,
    stream_key,
)
from whisperer.core.tasks.timing import StreamTiming

# §4.3: постановка ждёт Valkey не дольше 50 мс; операции воркера — не дольше секунды.
ENQUEUE_DEADLINE: Final = timedelta(milliseconds=50)
WORKER_CALL_DEADLINE: Final = timedelta(seconds=1)
DEAD_LETTER_RETENTION: Final = timedelta(days=7)
# Неразобранный за неделю провал уже не разберут; тысяча записей — предел памяти без вытеснения.
DEAD_LETTER_LIMIT: Final = 1000
DATA_FIELD: Final = b"data"
NO_GROUP: Final = "NOGROUP"
BUSY_GROUP: Final = "BUSYGROUP"
MILLISECOND: Final = timedelta(milliseconds=1)


class QueueFullError(Exception):
    """The stream holds as many unfinished tasks as it may; the task was not queued."""


class ConsumerGroupMissingError(Exception):
    """The consumer group is gone — Valkey was reset or failed over to an empty replica."""


@dataclass(frozen=True, slots=True)
class StreamEntry:
    """A message delivered to this consumer, and which delivery of it this is."""

    stream_id: str
    data: bytes | None
    delivery: int

    @property
    def enqueued_at(self) -> float:
        """Unix time the message entered the stream, from the time part of its id."""
        return int(self.stream_id.partition("-")[0]) / 1000


def milliseconds(duration: timedelta) -> int:
    """A duration in whole milliseconds, as stream commands take it."""
    return int(duration / MILLISECOND)


def as_text(value: object) -> str:
    """A reply string of Valkey, given as bytes or as text."""
    return value.decode() if isinstance(value, bytes) else str(value)


def stream_entries(reply: object) -> Iterator[tuple[str, bytes | None]]:
    """`(id, data)` of every entry in a reply of `XREADGROUP` or `XCLAIM`, in RESP2 or RESP3.

    The protocols wrap the same entries differently: RESP3 gives a mapping of stream
    names, RESP2 a list of `[name, entries]` pairs, `XCLAIM` a flat list of entries. The
    protocol is a setting of the connection, so the parser does not depend on it (draft
    lesson: a RESP2-only loop would have failed on the first message after a switch).
    """
    if isinstance(reply, dict):
        for nested in reply.values():
            yield from stream_entries(nested)
        return
    if not isinstance(reply, list | tuple):
        return
    if len(reply) == 2 and isinstance(reply[0], bytes | str) and isinstance(reply[1], dict):
        data = reply[1].get(DATA_FIELD)
        yield as_text(reply[0]), data if isinstance(data, bytes) else None
        return
    for item in reply:
        yield from stream_entries(item)


def raise_if_group_missing(error: ResponseError) -> None:
    """Turn the `NOGROUP` reply into `ConsumerGroupMissingError`; other replies stay errors."""
    if str(error).upper().startswith(NO_GROUP):
        raise ConsumerGroupMissingError from error


class TaskStream:
    """The stream of one queue as seen by one consumer of this process."""

    def __init__(
        self,
        client: Redis,
        queue: TaskQueue,
        timing: StreamTiming,
        consumer: str,
        *,
        capacity: int = STREAM_CAPACITY,
    ) -> None:
        self.queue = queue
        self.consumer = consumer
        self.timing = timing
        self._client = client
        self._capacity = capacity
        self._key = stream_key(queue)
        self._dead_key = dead_letter_key(queue)
        self._enqueue = client.register_script(scripts.ENQUEUE)
        self._renew = client.register_script(scripts.RENEW)
        self._acknowledge = client.register_script(scripts.ACKNOWLEDGE)
        self._retry_later = client.register_script(scripts.RETRY_LATER)
        self._dead_letter = client.register_script(scripts.DEAD_LETTER)

    async def enqueue(self, data: bytes) -> str:
        """Append a message within 50 ms; `QueueFullError` when the stream is at capacity."""
        async with asyncio.timeout(ENQUEUE_DEADLINE.total_seconds()):
            stream_id = await self._enqueue(keys=[self._key], args=[self._capacity, data])
        if stream_id is None:
            raise QueueFullError
        return as_text(stream_id)

    async def ensure_group(self) -> None:
        """Create the consumer group (and the stream) unless it exists."""
        try:
            async with asyncio.timeout(WORKER_CALL_DEADLINE.total_seconds()):
                await self._client.xgroup_create(self._key, CONSUMER_GROUP, id="0", mkstream=True)
        except ResponseError as error:
            if not str(error).upper().startswith(BUSY_GROUP):
                raise

    async def read(self) -> StreamEntry | None:
        """The next new message, waiting at most the blocking read time; None if none came."""
        deadline = self.timing.read_block + WORKER_CALL_DEADLINE
        try:
            async with asyncio.timeout(deadline.total_seconds()):
                reply = await self._client.xreadgroup(
                    CONSUMER_GROUP,
                    self.consumer,
                    {self._key: ">"},
                    count=1,
                    block=milliseconds(self.timing.read_block),
                )
        except ResponseError as error:
            raise_if_group_missing(error)
            raise
        for stream_id, data in stream_entries(reply):
            return StreamEntry(stream_id, data, delivery=1)
        return None

    async def claim_abandoned(self) -> StreamEntry | None:
        """Claim the oldest message idle longer than the lease, if there is one."""
        lease = milliseconds(self.timing.lease)
        try:
            async with asyncio.timeout(WORKER_CALL_DEADLINE.total_seconds()):
                pending = await self._client.xpending_range(
                    self._key, CONSUMER_GROUP, min="-", max="+", count=1, idle=lease
                )
                if not pending:
                    return None
                delivered = int(pending[0]["times_delivered"])
                # Тот же порог простоя: если сообщение уже забрал другой воркер или владелец
                # продлил аренду, захват не пройдёт — гонка решается в Valkey.
                claimed = await self._client.xclaim(
                    self._key, CONSUMER_GROUP, self.consumer, lease, [pending[0]["message_id"]]
                )
        except ResponseError as error:
            raise_if_group_missing(error)
            raise
        for stream_id, data in stream_entries(claimed):
            return StreamEntry(stream_id, data, delivery=delivered + 1)
        return None

    async def renew(self, stream_ids: Sequence[str]) -> set[str]:
        """Reset the idle time of messages still held by this consumer; return those ids."""
        async with asyncio.timeout(WORKER_CALL_DEADLINE.total_seconds()):
            kept = await self._renew(
                keys=[self._key], args=[CONSUMER_GROUP, self.consumer, *stream_ids]
            )
        return {as_text(stream_id) for stream_id in kept or []}

    async def acknowledge(self, stream_id: str) -> None:
        """Settle a finished message: acknowledge it and delete it from the stream."""
        async with asyncio.timeout(WORKER_CALL_DEADLINE.total_seconds()):
            await self._acknowledge(keys=[self._key], args=[CONSUMER_GROUP, stream_id])

    async def retry_later(self, stream_id: str, delay: timedelta) -> bool:
        """Make a held message claimable again after `delay`; False if it is no longer ours."""
        idle = max(milliseconds(self.timing.lease - delay), 0)
        async with asyncio.timeout(WORKER_CALL_DEADLINE.total_seconds()):
            moved = await self._retry_later(
                keys=[self._key], args=[CONSUMER_GROUP, self.consumer, stream_id, idle]
            )
        return int(moved) == 1

    async def dead_letter(self, stream_id: str, entry: str) -> bool:
        """Move a held message to the dead letter in one step; False if it is no longer ours."""
        oldest_kept = milliseconds(timedelta(seconds=time.time()) - DEAD_LETTER_RETENTION)
        async with asyncio.timeout(WORKER_CALL_DEADLINE.total_seconds()):
            moved = await self._dead_letter(
                keys=[self._key, self._dead_key],
                args=[
                    CONSUMER_GROUP,
                    self.consumer,
                    stream_id,
                    entry,
                    DEAD_LETTER_LIMIT,
                    f"{oldest_kept}-0",
                ],
            )
        return int(moved) == 1

    async def prune_consumers(self) -> int:
        """Forget consumers of finished processes; return how many were removed.

        A consumer name lives for one process, and Valkey remembers it forever. Only a
        consumer with no pending messages is removed: removing one with pending messages
        would drop its messages from the group without a trace (draft lesson).
        """
        stale = milliseconds(self.timing.consumer_stale_after)
        removed = 0
        try:
            async with asyncio.timeout(WORKER_CALL_DEADLINE.total_seconds()):
                consumers = await self._client.xinfo_consumers(self._key, CONSUMER_GROUP)
                for info in consumers:
                    name = as_text(info["name"])
                    if name == self.consumer or int(info["pending"]) or int(info["idle"]) < stale:
                        continue
                    await self._client.xgroup_delconsumer(self._key, CONSUMER_GROUP, name)
                    removed += 1
        except ResponseError as error:
            raise_if_group_missing(error)
            raise
        return removed
