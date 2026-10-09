"""A task system over the run's Valkey slot with fast time limits, and a worker to run it.

Production limits are minutes; the same mechanisms are tested with a lease of a second
and pauses of tens of milliseconds. Every helper waits with a bound, so a broken
mechanism fails the test instead of hanging the run.
"""

import asyncio
import json
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any
from uuid import UUID

import pytest
from opentelemetry.sdk.trace import TracerProvider
from prometheus_client import CollectorRegistry
from redis.asyncio import Redis

from shosai.core.tasks.broker import ValkeyStreamBroker
from shosai.core.tasks.declaration import (
    NO_RETRY,
    RetryPolicy,
    TaskDeclaration,
    TaskHandler,
    TaskKind,
)
from shosai.core.tasks.payloads import HomeTaskPayload, TaskPayload, TaskSecret
from shosai.core.tasks.queues import STREAM_CAPACITY, TaskQueue, dead_letter_key, stream_key
from shosai.core.tasks.sender import TaskSender
from shosai.core.tasks.stream import as_text
from shosai.core.tasks.system import StreamOptions, TaskSystem, build_task_system
from shosai.core.tasks.timing import Backoff, StreamTiming
from shosai.core.tasks.worker import consume_queue

WAIT_SECONDS = 10.0
POLL_SECONDS = 0.02
FAST = StreamTiming(
    lease=timedelta(seconds=1),
    renew_every=timedelta(milliseconds=200),
    recover_every=timedelta(milliseconds=50),
    read_block=timedelta(milliseconds=50),
    outage_pause=timedelta(milliseconds=50),
    backoff=Backoff(first=timedelta(milliseconds=50), ceiling=timedelta(milliseconds=200)),
)


class Probe(TaskPayload):
    """A payload with a note and, when given, a secret link."""

    note: str
    link: TaskSecret | None = None


class HomeProbe(HomeTaskPayload):
    """A home-scoped payload naming the row its task writes."""

    record_id: UUID


def declare(
    name: str,
    *,
    retry: RetryPolicy = NO_RETRY,
    kind: TaskKind = TaskKind.WORK,
    deadline: timedelta = timedelta(seconds=5),
    queue: TaskQueue = TaskQueue.DEFAULT,
) -> TaskDeclaration[Probe]:
    """A `Probe` task of the default queue."""
    return TaskDeclaration(
        name=name, queue=queue, payload=Probe, deadline=deadline, retry=retry, kind=kind
    )


@dataclass
class Runs:
    """What handlers ran, in order."""

    notes: list[str] = field(default_factory=list)

    def handler(
        self, task: TaskDeclaration[Probe], failure: Exception | None = None, seconds: float = 0
    ) -> TaskHandler[Probe]:
        """A handler recording each run, sleeping `seconds`, then raising `failure` if given."""

        async def handle(payload: Probe) -> None:
            self.notes.append(payload.note)
            if seconds:
                await asyncio.sleep(seconds)
            if failure is not None:
                raise failure

        return TaskHandler(task, handle)


@dataclass(frozen=True, slots=True)
class Workbench:
    """One process's task system over the slot's Valkey database."""

    client: Redis
    system: TaskSystem
    registry: CollectorRegistry

    def broker(self, queue: TaskQueue = TaskQueue.DEFAULT) -> ValkeyStreamBroker:
        """The broker of a queue."""
        return self.system.brokers[queue]

    def sample(self, name: str, **labels: str) -> float:
        """A metric sample, 0 when it was never recorded."""
        return self.registry.get_sample_value(name, labels) or 0.0

    async def dead_letters(self, queue: TaskQueue = TaskQueue.DEFAULT) -> list[dict[str, Any]]:
        """The queue's dead-letter entries, oldest first."""
        return [
            json.loads(fields[b"entry"])
            for _, fields in await stream_entries_of(self.client, dead_letter_key(queue))
        ]

    async def depth(self, queue: TaskQueue = TaskQueue.DEFAULT) -> int:
        """Unfinished tasks in the queue's stream."""
        return int(await self.client.xlen(stream_key(queue)))


type Fields = dict[bytes | str, bytes | str]
# Обработчики, построенные с отправителем стенда: так их строит композиция процесса.
type HandlerBinding = Callable[[TaskSender], Sequence[TaskHandler[Any]]]


async def stream_entries_of(client: Redis, key: str) -> list[tuple[str, Fields]]:
    """`(id, fields)` of every entry of a stream, oldest first; none when it does not exist."""
    reply = await client.xrange(key) or []
    return [(as_text(stream_id), dict(fields or {})) for stream_id, fields in reply]


def workbench(
    client: Redis,
    handlers: Sequence[TaskHandler[Any]],
    *,
    consumer: str = "worker-a",
    tracer_provider: TracerProvider | None = None,
    capacity: int = STREAM_CAPACITY,
) -> Workbench:
    """A task system with fast limits and its own metrics registry."""
    options = StreamOptions(timing=FAST, consumer=consumer, capacity=capacity)
    return assemble(client, lambda _sender: handlers, CollectorRegistry(), tracer_provider, options)


def bound_workbench(
    client: Redis,
    bind_handlers: HandlerBinding,
    registry: CollectorRegistry,
    *,
    consumer: str = "worker-a",
    tracer_provider: TracerProvider | None = None,
) -> Workbench:
    """A task system with fast limits whose handlers are bound to its own sender."""
    options = StreamOptions(timing=FAST, consumer=consumer)
    return assemble(client, bind_handlers, registry, tracer_provider, options)


def assemble(
    client: Redis,
    bind_handlers: HandlerBinding,
    registry: CollectorRegistry,
    tracer_provider: TracerProvider | None,
    options: StreamOptions,
) -> Workbench:
    """The task system and the registry its metrics went to."""
    system = build_task_system(client, registry, tracer_provider or TracerProvider(), options)
    system.register(bind_handlers(system.sender))
    return Workbench(client, system, registry)


@asynccontextmanager
async def running(
    broker: ValkeyStreamBroker, drain: timedelta = timedelta(seconds=2)
) -> AsyncIterator[asyncio.Event]:
    """A worker consuming the broker's queue until the block ends; the stop event is given."""
    stop = asyncio.Event()
    worker = asyncio.create_task(consume_queue(broker, stop, drain=drain))
    try:
        yield stop
    finally:
        stop.set()
        await asyncio.wait_for(worker, WAIT_SECONDS)


type Check = Callable[[], Awaitable[bool]]


def settled(bench: Workbench, task: str, outcome: str, at_least: int = 1) -> Check:
    """Holds once `at_least` runs of the default-queue task ended with `outcome`."""

    async def check() -> bool:
        runs = bench.sample("shosai_task_runs_total", queue="default", task=task, outcome=outcome)
        return runs >= at_least

    return check


def counted(bench: Workbench, name: str, **labels: str) -> Check:
    """Holds once the metric sample is at least 1."""

    async def check() -> bool:
        return bench.sample(name, **labels) >= 1

    return check


def absent(client: Redis, key: str) -> Check:
    """Holds once the key no longer exists."""

    async def check() -> bool:
        return int(await client.exists(key)) == 0

    return check


async def eventually(check: Check, within: float = WAIT_SECONDS) -> None:
    """Wait until `check` holds; fail the test when it does not within the bound."""
    deadline = time.monotonic() + within
    while not await check():
        if time.monotonic() > deadline:
            pytest.fail(f"условие не выполнилось за {within} с", pytrace=False)
        await asyncio.sleep(POLL_SECONDS)
