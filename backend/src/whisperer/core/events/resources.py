"""What the event tasks of a process are built with; composition passes it in."""

from dataclasses import dataclass, field

from opentelemetry.sdk.trace import TracerProvider

from whisperer.core.db.transactions import HomeTransactions
from whisperer.core.events.catalog import EventCatalog
from whisperer.core.events.metrics import EventMetrics
from whisperer.core.events.purge import Retention
from whisperer.core.events.relay_limits import RelayLimits


@dataclass(frozen=True, slots=True)
class EventResources:
    """The catalog, the home transactions, the metrics and tracing, and the time limits."""

    catalog: EventCatalog
    transactions: HomeTransactions
    metrics: EventMetrics
    tracer_provider: TracerProvider
    relay_limits: RelayLimits = field(default_factory=RelayLimits)
    retention: Retention = field(default_factory=Retention)
