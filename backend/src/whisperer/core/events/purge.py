"""Removal of published events and old delivery marks after their retention (§8.1, F1-C5).

Published outbox rows stay 7 days for diagnosis; delivery marks stay 14, longer than any
redelivery of their event can arrive. Unpublished rows are never removed: an event that
cannot be passed on is an alert, not garbage. Rows go in batches of 5 000, each batch in
its own transaction, so the purge holds no long lock and no large transaction.
"""

from dataclasses import dataclass
from datetime import timedelta

import structlog
from sqlalchemy import Delete, delete, func, select, tuple_

from whisperer.core.db.transactions import HomeTransactions
from whisperer.core.events.metrics import EventMetrics, PurgedTable
from whisperer.core.events.records import OutboxMessage, ProcessedEvent
from whisperer.core.kernel.homes import Home
from whisperer.core.kernel.tenancy import TenancyScope

log = structlog.stdlib.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class Retention:
    """How long published events and delivery marks are kept, and the batch of one delete."""

    published_events: timedelta = timedelta(days=7)
    delivery_marks: timedelta = timedelta(days=14)
    batch: int = 5_000

    def __post_init__(self) -> None:
        if self.delivery_marks <= self.published_events:
            message = "отметки доставки живут дольше опубликованных событий"
            raise ValueError(message)


@dataclass(frozen=True, slots=True)
class PurgeResult:
    """Rows removed from each table in one purge."""

    published_events: int
    delivery_marks: int


class OutboxPurge:
    """Removes the expired rows of a home's outbox and delivery marks."""

    def __init__(
        self,
        transactions: HomeTransactions,
        metrics: EventMetrics,
        retention: Retention | None = None,
    ) -> None:
        self._transactions = transactions
        self._metrics = metrics
        self._retention = retention or Retention()

    async def purge(self, home: Home) -> PurgeResult:
        """Remove every expired row of the home, batch by batch."""
        retention = self._retention
        expired_events = (
            select(OutboxMessage.id)
            .where(OutboxMessage.published_at < func.now() - retention.published_events)
            .limit(retention.batch)
        )
        expired_marks = (
            select(ProcessedEvent.consumer, ProcessedEvent.event_id)
            .where(ProcessedEvent.processed_at < func.now() - retention.delivery_marks)
            .limit(retention.batch)
        )
        result = PurgeResult(
            published_events=await self._remove(
                home,
                "outbox_messages",
                delete(OutboxMessage).where(OutboxMessage.id.in_(expired_events)),
            ),
            delivery_marks=await self._remove(
                home,
                "processed_events",
                delete(ProcessedEvent).where(
                    tuple_(ProcessedEvent.consumer, ProcessedEvent.event_id).in_(expired_marks)
                ),
            ),
        )
        log.info(
            "Удалены строки outbox и отметки доставки по сроку хранения",
            home=home.value,
            published_events=result.published_events,
            delivery_marks=result.delivery_marks,
        )
        return result

    async def _remove(self, home: Home, table: PurgedTable, statement: Delete) -> int:
        removed = 0
        while True:
            async with self._transactions.begin(TenancyScope(home)) as session:
                # Через соединение: оператор ядра, а не ORM, и известно число удалённых строк.
                connection = await session.connection()
                count = (await connection.execute(statement)).rowcount
            removed += count
            if count:
                self._metrics.count_purged(home, table, count)
            if count < self._retention.batch:
                return removed
