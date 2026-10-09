"""Events, subscriptions and an event system over the run's slot, for the event tests.

Each consumer writes its effect — one row of the probe table, which has company
isolation — in the delivery's transaction, so a test sees what was applied, how often,
in which home and under which tenancy scope.
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import timedelta
from enum import StrEnum
from typing import Any, ClassVar
from uuid import UUID

import sqlalchemy as sa
from opentelemetry.sdk.trace import TracerProvider
from prometheus_client import CollectorRegistry
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.events.catalog import EventCatalog
from shosai.core.events.domain_event import DomainEvent, EventCode
from shosai.core.events.metrics import EventMetrics
from shosai.core.events.outbox import EventOutbox
from shosai.core.events.relay_limits import RelayLimits
from shosai.core.events.resources import EventResources
from shosai.core.events.subscriptions import EventSubscription, ReceivedEvent
from shosai.core.events.system import event_task_handlers
from shosai.core.tasks.queues import TaskQueue
from tests.core.db.probe_table import probe_records
from tests.core.tasks.workbench import Check, Workbench, bound_workbench
from tests.harness.connections import Connection, fetch_rows
from tests.harness.database_access import DatabaseAccess

DEADLINE = timedelta(seconds=10)


class NoteState(StrEnum):
    """A closed set of states a probe note reports."""

    DRAFT = "draft"
    FINAL = "final"


class NoteWritten(DomainEvent):
    """A probe note was written."""

    event_type: ClassVar[str] = "probe.note.written"
    version: ClassVar[int] = 1

    record_id: UUID
    state: NoteState
    reason: EventCode | None = None


class NoteArchived(DomainEvent):
    """A probe note was archived; listed without subscribers in some tests."""

    event_type: ClassVar[str] = "probe.note.archived"
    version: ClassVar[int] = 1

    record_id: UUID


@dataclass
class Applied:
    """What consumers applied, in order: the consumer and the event as it arrived."""

    events: list[tuple[str, ReceivedEvent[NoteWritten]]] = field(default_factory=list)

    def consumers(self) -> list[str]:
        """Consumer names in the order they applied events."""
        return [consumer for consumer, _ in self.events]


def effect_id(received: ReceivedEvent[Any], consumer: str) -> UUID:
    """The id of the probe row a consumer writes for an event."""
    return uuid.uuid5(received.event_id, consumer)


def recording(
    consumer: str,
    applied: Applied,
    *,
    queue: TaskQueue = TaskQueue.DEFAULT,
    failures: list[Exception] | None = None,
) -> EventSubscription[NoteWritten]:
    """A consumer that writes its probe row; it raises the given failures first, one per run."""
    pending = failures if failures is not None else []

    async def handle(session: AsyncSession, received: ReceivedEvent[NoteWritten]) -> None:
        applied.events.append((consumer, received))
        await session.execute(
            sa.insert(probe_records).values(
                id=effect_id(received, consumer), org_id=received.scope.org_id, note=consumer
            )
        )
        if pending:
            raise pending.pop(0)

    return EventSubscription(
        consumer=consumer, event=NoteWritten, queue=queue, deadline=DEADLINE, handle=handle
    )


@dataclass(frozen=True, slots=True)
class EventBench:
    """One process's event system: resources, the writer and the task system."""

    resources: EventResources
    outbox: EventOutbox
    tasks: Workbench

    def sample(self, name: str, **labels: str) -> float:
        """A metric sample of the process, 0 when it was never recorded."""
        return self.tasks.sample(name, **labels)


def event_bench(
    valkey: Redis,
    homes: DatabaseAccess,
    subscriptions: Sequence[EventSubscription[Any]] = (),
    *,
    tracer_provider: TracerProvider | None = None,
    relay_limits: RelayLimits | None = None,
) -> EventBench:
    """An event system listing both probe events, with fast task time limits."""
    registry = CollectorRegistry()
    resources = EventResources(
        catalog=EventCatalog([NoteWritten, NoteArchived], subscriptions),
        transactions=homes.transactions,
        metrics=EventMetrics(registry),
        tracer_provider=tracer_provider or TracerProvider(),
        relay_limits=relay_limits or RelayLimits(),
    )
    tasks = bound_workbench(
        valkey,
        lambda sender: event_task_handlers(resources, sender),
        registry,
        tracer_provider=tracer_provider,
    )
    return EventBench(resources, EventOutbox(resources.catalog), tasks)


def runs(bench: EventBench, queue: TaskQueue, task: str, outcome: str, at_least: int = 1) -> Check:
    """Holds once `at_least` runs of the task in the queue ended with `outcome`."""

    async def check() -> bool:
        sample = bench.sample(
            "shosai_task_runs_total", queue=queue.value, task=task, outcome=outcome
        )
        return sample >= at_least

    return check


async def outbox_rows(connection: Connection) -> list[dict[str, Any]]:
    """Every outbox row of a home with its relay state, oldest first."""
    rows = await fetch_rows(
        connection,
        "SELECT id, event_type, attempts, published_at IS NOT NULL AS published, "
        "extract(epoch FROM available_at - now())::float AS due_in "
        "FROM outbox_messages ORDER BY id",
    )
    return [dict(row) for row in rows]


async def insert_raw_event(
    connection: Connection, event_type: str, *, age: timedelta = timedelta(0)
) -> UUID:
    """An outbox row written past the writer, as another image or an older run would leave it."""
    event_id = uuid.uuid7()
    await connection.execute(
        "INSERT INTO outbox_messages (id, event_type, version, payload, occurred_at) "
        "VALUES (%s, %s, 1, '{}'::jsonb, now() - %s)",
        (event_id, event_type, age),
    )
    return event_id
