"""Delivery of one event to one consumer: a task per subscription (target architecture §12).

The relay queues the event to the task of each subscriber; the task carries the event
itself, so the delivery reads nothing back from the outbox (one round trip less to the
Russian home), and the event's home and tenancy, so the delivery opens its transaction
where the effect was committed. In that transaction it first writes the delivery mark
`(consumer, event_id)`: a mark that already exists means the event was applied, and the
handler does not run again. Mark and effect commit together or not at all.

A consumer this process does not know is a task this process does not know: the broker
dead-letters and counts it (§14 rule 9). A payload the consumer's event class cannot read
is dead-lettered as well; another delivery would not make it readable.
"""

from datetime import datetime
from uuid import UUID

import structlog
from pydantic import JsonValue, ValidationError
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from whisperer.core.db.transactions import HomeTransactions
from whisperer.core.events.domain_event import DomainEvent
from whisperer.core.events.metrics import EventMetrics
from whisperer.core.events.records import ProcessedEvent
from whisperer.core.events.subscriptions import EventSubscription, ReceivedEvent
from whisperer.core.observability.log_context import LogFields
from whisperer.core.tasks.declaration import RETRY_TRANSIENT, TaskDeclaration, TaskHandler
from whisperer.core.tasks.errors import InvalidTaskPayloadError
from whisperer.core.tasks.handlers import validation_problems
from whisperer.core.tasks.payloads import HomeTaskPayload

log = structlog.stdlib.get_logger(__name__)


class EventDeliveryPayload(HomeTaskPayload):
    """One event on its way to one consumer: the outbox row without its relay state."""

    event_id: UUID
    event_type: str
    version: int
    occurred_at: datetime
    event: dict[str, JsonValue]

    def log_fields(self) -> LogFields:
        """The home, the account, the company and the event."""
        fields = super().log_fields()
        fields["event_id"] = self.event_id
        return fields


def delivery_task[E: DomainEvent](
    subscription: EventSubscription[E],
) -> TaskDeclaration[EventDeliveryPayload]:
    """The task that delivers events to the subscription's consumer.

    A delivery may run again — the mark makes a repeat harmless — so failures of the home,
    the bucket, Valkey or the network earn another delivery.
    """
    return TaskDeclaration(
        name=subscription.task_name,
        queue=subscription.queue,
        payload=EventDeliveryPayload,
        deadline=subscription.deadline,
        retry=RETRY_TRANSIENT,
    )


def received_event[E: DomainEvent](
    subscription: EventSubscription[E], payload: EventDeliveryPayload
) -> ReceivedEvent[E]:
    """The event as the consumer's class reads it; problems name fields, never values."""
    if payload.event_type != subscription.event.event_type:
        problems = [f"event_type: expected {subscription.event.event_type}"]
        raise InvalidTaskPayloadError(subscription.task_name, problems)
    try:
        event = subscription.event.model_validate(payload.event)
    except ValidationError as error:
        problems = [f"event.{problem}" for problem in validation_problems(error)]
        raise InvalidTaskPayloadError(subscription.task_name, problems) from None
    return ReceivedEvent(
        event=event,
        event_id=payload.event_id,
        version=payload.version,
        occurred_at=payload.occurred_at,
        scope=payload.scope(),
    )


async def mark_processed(session: AsyncSession, consumer: str, event_id: UUID) -> bool:
    """Write the delivery mark; False when the consumer has already applied the event."""
    statement = (
        insert(ProcessedEvent)
        .values(consumer=consumer, event_id=event_id)
        .on_conflict_do_nothing()
        .returning(ProcessedEvent.event_id)
    )
    marked = (await session.execute(statement)).scalar_one_or_none()
    return marked is not None


def delivery_handler[E: DomainEvent](
    subscription: EventSubscription[E],
    task: TaskDeclaration[EventDeliveryPayload],
    transactions: HomeTransactions,
    metrics: EventMetrics,
) -> TaskHandler[EventDeliveryPayload]:
    """The task handler that applies each delivered event once."""

    async def deliver(payload: EventDeliveryPayload) -> None:
        received = received_event(subscription, payload)
        async with transactions.begin(received.scope) as session:
            if not await mark_processed(session, subscription.consumer, received.event_id):
                metrics.count_duplicate(subscription.consumer)
                log.info(
                    "Событие уже применено потребителем: повтор пропущен",
                    consumer=subscription.consumer,
                    event_type=payload.event_type,
                )
                return
            await subscription.handle(session, received)

    return TaskHandler(task, deliver)
