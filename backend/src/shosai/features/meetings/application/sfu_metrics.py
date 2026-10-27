"""LiveKit's load as the admin's screen reads it: nodes, traffic and a day's history (MR-D10).

LiveKit's server API knows rooms and participants but not its nodes or traffic; those come
from the observability stack's Prometheus, which scrapes LiveKit. Prometheus may be down or
may not scrape LiveKit yet: then the answer is "no data" — no nodes, no traffic, an empty
history — never a guess.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final, Protocol

HISTORY_SPAN: Final = timedelta(hours=24)
HISTORY_STEP: Final = timedelta(minutes=15)


@dataclass(frozen=True, slots=True)
class NodeLoad:
    """One LiveKit node as Prometheus last scraped it.

    `cpu_percent` is the share of the CPUs the node's Go runtime may use; `memory_bytes` is
    its resident memory. A node Prometheus could not scrape is down, with no load.
    """

    id: str
    up: bool
    rooms: int = 0
    participants: int = 0
    cpu_percent: float | None = None
    memory_bytes: int | None = None


@dataclass(frozen=True, slots=True)
class LoadNow:
    """LiveKit's load at this moment, across its nodes."""

    started_at: datetime | None
    published_tracks: int
    bandwidth_in_mbps: float
    bandwidth_out_mbps: float
    nodes: tuple[NodeLoad, ...]


@dataclass(frozen=True, slots=True)
class LoadSample:
    """One sample of the day's history."""

    at: datetime
    participants: int
    bandwidth_in_mbps: float
    bandwidth_out_mbps: float


class SfuMetrics(Protocol):
    """LiveKit's load from the metrics store."""

    async def now(self) -> LoadNow | None:
        """The load at this moment; None when the store does not answer or knows no node."""
        ...

    async def history(self, until: datetime) -> Sequence[LoadSample]:
        """A sample every `HISTORY_STEP` over `HISTORY_SPAN` up to `until`, oldest first;
        empty when the store does not answer."""
        ...
