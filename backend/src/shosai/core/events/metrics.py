"""Metrics of the outbox and of event deliveries (target architecture §16.4, §16.7).

Labels come from closed sets: the home, the reason a row was held back, the table and
the consumer — a name some slice declared. The pending gauges are properties of a home's
database, set by one process (the scheduler), not by every worker. The monitor "outbox
events older than 5 min" (§16.4) pages on `shosai_outbox_oldest_age_seconds`.
"""

from typing import Literal

from prometheus_client import CollectorRegistry, Counter, Gauge

from shosai.core.kernel.homes import Home

type HoldBackReason = Literal["queue_unavailable", "unknown_event_type", "unregistered_delivery"]
type PurgedTable = Literal["outbox_messages", "processed_events"]
HOME_LABEL = ("home",)


class EventMetrics:
    """Counters of the relay, the purge and the deliveries, and the outbox gauges."""

    def __init__(self, registry: CollectorRegistry) -> None:
        self._published = Counter(
            "shosai_outbox_published",
            "События outbox, доставки которых поставлены в очереди",
            HOME_LABEL,
            registry=registry,
        )
        self._held_back = Counter(
            "shosai_outbox_held_back",
            "События outbox, отложенные relay с паузой: доставки не поставлены",
            ("home", "reason"),
            registry=registry,
        )
        self._purged = Counter(
            "shosai_outbox_purged_rows",
            "Строки outbox и отметок доставки, удалённые по сроку хранения",
            ("home", "table"),
            registry=registry,
        )
        self._duplicates = Counter(
            "shosai_event_duplicate_deliveries",
            "Повторные доставки событий, пропущенные по отметке потребителя",
            ("consumer",),
            registry=registry,
        )
        self.pending = Gauge(
            "shosai_outbox_pending",
            "Неопубликованные события outbox дома",
            HOME_LABEL,
            registry=registry,
        )
        self.oldest_age = Gauge(
            "shosai_outbox_oldest_age_seconds",
            "Возраст самого старого неопубликованного события outbox дома",
            HOME_LABEL,
            registry=registry,
        )

    def count_published(self, home: Home, count: int) -> None:
        """Events whose deliveries the relay queued."""
        self._published.labels(home=home.value).inc(count)

    def count_held_back(self, home: Home, reason: HoldBackReason) -> None:
        """One event the relay could not pass on and will retry after a pause."""
        self._held_back.labels(home=home.value, reason=reason).inc()

    def count_purged(self, home: Home, table: PurgedTable, count: int) -> None:
        """Rows removed after their retention."""
        self._purged.labels(home=home.value, table=table).inc(count)

    def count_duplicate(self, consumer: str) -> None:
        """One delivery of an event the consumer had already applied."""
        self._duplicates.labels(consumer=consumer).inc()

    def set_pending(self, home: Home, count: int, oldest_age_seconds: float) -> None:
        """The unpublished events of a home and the age of the oldest one."""
        self.pending.labels(home=home.value).set(count)
        self.oldest_age.labels(home=home.value).set(oldest_age_seconds)
