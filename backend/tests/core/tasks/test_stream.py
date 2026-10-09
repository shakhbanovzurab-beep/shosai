"""The queue stream in Valkey: bounded, settled atomically, changed only by its holder."""

import asyncio
from dataclasses import replace
from datetime import timedelta

import pytest
from redis.asyncio import Redis

from shosai.core.tasks.queues import CONSUMER_GROUP, TaskQueue, dead_letter_key, stream_key
from shosai.core.tasks.stream import (
    ConsumerGroupMissingError,
    QueueFullError,
    StreamEntry,
    TaskStream,
    as_text,
    stream_entries,
)
from tests.core.tasks.workbench import FAST, stream_entries_of

QUEUE = TaskQueue.BULK
LEASE_SECONDS = FAST.lease.total_seconds()


def stream_of(client: Redis, consumer: str = "worker-a", capacity: int = 10) -> TaskStream:
    return TaskStream(client, QUEUE, FAST, consumer, capacity=capacity)


async def received(stream: TaskStream) -> StreamEntry:
    entry = await stream.read()
    assert entry is not None
    return entry


async def pending(client: Redis) -> list[tuple[str, str, int]]:
    """(id, consumer, deliveries) of every pending message."""
    entries = await client.xpending_range(
        stream_key(QUEUE), CONSUMER_GROUP, min="-", max="+", count=100
    )
    return [
        (as_text(item["message_id"]), as_text(item["consumer"]), int(item["times_delivered"]))
        for item in entries
    ]


async def test_a_message_is_read_once_and_deleted_when_acknowledged(valkey: Redis) -> None:
    stream = stream_of(valkey)
    await stream.ensure_group()
    stream_id = await stream.enqueue(b"one")

    entry = await received(stream)
    assert entry == StreamEntry(stream_id, b"one", delivery=1)
    assert await stream.read() is None

    await stream.acknowledge(stream_id)
    assert await valkey.xlen(stream_key(QUEUE)) == 0
    assert await pending(valkey) == []


async def test_the_group_reads_messages_queued_before_it_existed(valkey: Redis) -> None:
    stream = stream_of(valkey)
    await stream.enqueue(b"early")
    await stream.ensure_group()
    await stream.ensure_group()

    assert (await received(stream)).data == b"early"


async def test_a_full_stream_refuses_instead_of_dropping_old_tasks(valkey: Redis) -> None:
    stream = stream_of(valkey, capacity=2)
    first = await stream.enqueue(b"1")
    await stream.enqueue(b"2")

    with pytest.raises(QueueFullError):
        await stream.enqueue(b"3")

    entries = await stream_entries_of(valkey, stream_key(QUEUE))
    assert [stream_id for stream_id, _ in entries][:1] == [first]
    assert len(entries) == 2


async def test_reading_without_the_group_says_so(valkey: Redis) -> None:
    with pytest.raises(ConsumerGroupMissingError):
        await stream_of(valkey).read()


async def test_an_abandoned_message_is_claimed_after_the_lease_as_a_new_delivery(
    valkey: Redis,
) -> None:
    dead, alive = stream_of(valkey, "worker-dead"), stream_of(valkey, "worker-alive")
    await dead.ensure_group()
    stream_id = await dead.enqueue(b"work")
    await received(dead)

    assert await alive.claim_abandoned() is None
    await asyncio.sleep(LEASE_SECONDS + 0.1)

    assert await alive.claim_abandoned() == StreamEntry(stream_id, b"work", delivery=2)
    assert await pending(valkey) == [(stream_id, "worker-alive", 2)]


async def test_a_renewed_lease_keeps_the_message_with_its_holder(valkey: Redis) -> None:
    holder, other = stream_of(valkey, "worker-a"), stream_of(valkey, "worker-b")
    await holder.ensure_group()
    stream_id = await holder.enqueue(b"long")
    await received(holder)

    for _ in range(3):
        await asyncio.sleep(LEASE_SECONDS / 2)
        assert await holder.renew([stream_id]) == {stream_id}
        assert await other.claim_abandoned() is None

    assert await pending(valkey) == [(stream_id, "worker-a", 1)]
    assert await other.renew([stream_id]) == set()


async def test_a_retry_makes_the_message_claimable_after_its_pause(valkey: Redis) -> None:
    holder, other = stream_of(valkey, "worker-a"), stream_of(valkey, "worker-b")
    await holder.ensure_group()
    stream_id = await holder.enqueue(b"retry")
    await received(holder)

    assert not await other.retry_later(stream_id, timedelta(milliseconds=300))
    assert await holder.retry_later(stream_id, timedelta(milliseconds=300))
    assert await other.claim_abandoned() is None
    await asyncio.sleep(0.4)

    assert await other.claim_abandoned() == StreamEntry(stream_id, b"retry", delivery=2)


async def test_only_the_holder_moves_a_message_to_the_dead_letter(valkey: Redis) -> None:
    holder, other = stream_of(valkey, "worker-a"), stream_of(valkey, "worker-b")
    await holder.ensure_group()
    stream_id = await holder.enqueue(b"poison")
    await received(holder)

    assert not await other.dead_letter(stream_id, '{"reason":"failed"}')
    assert await valkey.xlen(dead_letter_key(QUEUE)) == 0

    assert await holder.dead_letter(stream_id, '{"reason":"failed"}')
    [(_, fields)] = await stream_entries_of(valkey, dead_letter_key(QUEUE))
    assert fields == {b"entry": b'{"reason":"failed"}'}
    assert await valkey.xlen(stream_key(QUEUE)) == 0
    assert await pending(valkey) == []


async def test_only_finished_consumers_without_pending_messages_are_forgotten(
    valkey: Redis,
) -> None:
    current = TaskStream(valkey, QUEUE, replace(FAST, consumer_stale_after=timedelta(0)), "me")
    busy, idle = stream_of(valkey, "busy"), stream_of(valkey, "idle")
    await current.ensure_group()
    await busy.enqueue(b"held")
    await received(busy)
    assert await idle.read() is None
    await asyncio.sleep(0.01)

    assert await current.prune_consumers() == 1
    consumers = await valkey.xinfo_consumers(stream_key(QUEUE), CONSUMER_GROUP)
    assert sorted(info["name"].decode() for info in consumers) == ["busy"]


@pytest.mark.parametrize(
    "reply",
    [
        [[b"shosai:tasks:bulk", [(b"1-0", {b"data": b"x"})]]],
        {b"shosai:tasks:bulk": [[(b"1-0", {b"data": b"x"})]]},
        [(b"1-0", {b"data": b"x"})],
    ],
)
def test_entries_are_read_from_either_protocol(reply: object) -> None:
    assert list(stream_entries(reply)) == [("1-0", b"x")]


def test_an_entry_without_a_body_or_a_deleted_entry_is_told_apart() -> None:
    assert list(stream_entries([(b"1-0", {b"other": b"x"})])) == [("1-0", None)]
    assert list(stream_entries([(b"1-0", None)])) == []
    assert list(stream_entries([])) == []
