"""Writing an event into the outbox, inside the transaction of its effect (§12, §14 rule 3).

The database and the queue share no transaction: sending a task after the commit loses
the work when the process dies in between, sending it before the commit announces an
effect that may roll back (draft lessons: lost calendar updates, welcome emails for
registrations that failed). The event is therefore a row in the effect's transaction —
both exist or neither does — and the relay passes it on later.

The writer commits nothing. It takes the home and tenancy from the transaction itself,
and keeps the trace context and the request id of the unit of work, so the deliveries
continue the producer's trace and log lines (§16.2).
"""

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

import structlog
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import transaction_info
from shosai.core.events.domain_event import DomainEvent
from shosai.core.events.records import OutboxMessage
from shosai.core.kernel.ids import new_id
from shosai.core.observability.log_context import bound_request_id, id_fields

TRACEPARENT = "traceparent"
log = structlog.stdlib.get_logger(__name__)


class UnlistedEventError(Exception):
    """An event whose class composition did not list: nobody could route it."""

    def __init__(self, event_type: str) -> None:
        super().__init__(f"событие {event_type} не перечислено в каталоге событий")


class ReadOnlyEventTransactionError(Exception):
    """An event written in a read-only transaction: it reports no effect."""

    def __init__(self, event_type: str) -> None:
        super().__init__(f"событие {event_type} пишется в транзакции только для чтения")


def current_traceparent() -> str | None:
    """The W3C `traceparent` of the current span, if there is one."""
    carrier: dict[str, str] = {}
    TraceContextTextMapPropagator().inject(carrier)
    return carrier.get(TRACEPARENT)


class ListedEvents(Protocol):
    """The event classes composition listed: `EventTypes` or the full `EventCatalog`."""

    def lists(self, event: DomainEvent) -> bool:
        """Whether the event's class is the one listed for its type."""
        ...


class EventOutbox:
    """Writes events into the caller's transaction; slices receive it by injection."""

    def __init__(self, catalog: ListedEvents) -> None:
        self._catalog = catalog

    async def add(self, session: AsyncSession, event: DomainEvent) -> UUID:
        """Add the event to the session's transaction; return its id. Commits nothing."""
        [event_id] = await self.add_all(session, [event])
        return event_id

    async def add_all(self, session: AsyncSession, events: Sequence[DomainEvent]) -> list[UUID]:
        """Add the events to the session's transaction in one statement; their ids, in order.

        One change of many records (a folder's files) writes its events in one round trip.
        Commits nothing; an empty list writes nothing.
        """
        for event in events:
            if not self._catalog.lists(event):
                raise UnlistedEventError(event.event_type)
        if not events:
            return []
        transaction = transaction_info(session)
        if transaction.read_only:
            raise ReadOnlyEventTransactionError(events[0].event_type)
        scope = transaction.scope
        traceparent, request_id = current_traceparent(), bound_request_id()
        ids = [new_id() for _ in events]
        rows = [
            {
                "id": event_id,
                "event_type": event.event_type,
                "version": event.version,
                "payload": event.model_dump(mode="json"),
                "user_id": scope.user_id,
                "org_id": scope.org_id,
                "traceparent": traceparent,
                "request_id": request_id,
            }
            for event_id, event in zip(ids, events, strict=True)
        ]
        await session.execute(insert(OutboxMessage), rows)
        for event_id, event in zip(ids, events, strict=True):
            log.debug(
                "Событие записано в транзакцию", event_type=event.event_type,
                event_id=str(event_id), **id_fields(user_id=scope.user_id, org_id=scope.org_id),
            )  # fmt: skip
        return ids
