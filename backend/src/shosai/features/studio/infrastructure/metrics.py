"""Studio's metrics (studio plan §3.7): the catalogue's daily refresh and what it found.

Counters survive a worker's restart in the rules that read them (`increase`), unlike a gauge
the next process would start at zero: the refresh adds the defaults that cannot answer and the
tier proposals left waiting every day it finds them, and the ticket rules watch the last day.
"""

from enum import StrEnum
from typing import Final

from prometheus_client import CollectorRegistry, Counter

REFRESHES: Final = "shosai_studio_catalogue_refresh_total"
BROKEN_DEFAULTS: Final = "shosai_studio_broken_defaults_total"
WAITING_PROPOSALS: Final = "shosai_studio_waiting_tier_proposals_total"


class RefreshOutcome(StrEnum):
    """How a refresh of the catalogue ended."""

    DONE = "done"
    UNREADABLE = "unreadable"
    # Список не досчитался заметной доли каталога: такой список не выключает ни одной модели.
    FUSED = "fused"


class BrokenDefault(StrEnum):
    """Why a role's default or fallback cannot answer."""

    UNLISTED = "unlisted"
    CANNOT_SERVE = "cannot_serve"


class StudioMetrics:
    """The counters of the catalogue's refresh."""

    def __init__(self, registry: CollectorRegistry) -> None:
        self._refreshes = Counter(
            REFRESHES, "Refreshes of the catalogue by outcome", ["outcome"], registry=registry
        )
        self._broken = Counter(
            BROKEN_DEFAULTS,
            "Role defaults and fallbacks found unable to answer, per refresh",
            ["reason"],
            registry=registry,
        )
        self._waiting = Counter(
            WAITING_PROPOSALS,
            "Tier proposals found waiting for the admin over three days, per refresh",
            registry=registry,
        )
        # Серии с нулём с самого старта: `increase` в правилах тикетов видит первый проход.
        for outcome in RefreshOutcome:
            self._refreshes.labels(outcome=outcome.value)
        for reason in BrokenDefault:
            self._broken.labels(reason=reason.value)

    def refreshed(self, outcome: RefreshOutcome) -> None:
        """Count one refresh."""
        self._refreshes.labels(outcome=outcome.value).inc()

    def broken(self, reason: BrokenDefault, count: int) -> None:
        """Count the defaults a refresh found unable to answer."""
        if count:
            self._broken.labels(reason=reason.value).inc(count)

    def waiting(self, count: int) -> None:
        """Count the proposals a refresh found waiting too long."""
        if count:
            self._waiting.inc(count)
