"""Metrics of the home databases of one process (target architecture §16.5, §16.6).

Occupancy is read from the pools when Prometheus scrapes, so it costs nothing per request;
the ticket threshold is 70% in either home. A transaction that got no connection — the
pool wait ran out or the home did not answer — is counted by home and reason. The state
of each home's check pages when a database is another home's or behind the code.
"""

from collections.abc import Iterator
from typing import Literal

from prometheus_client import CollectorRegistry, Counter, Enum
from prometheus_client.core import GaugeMetricFamily, Metric
from prometheus_client.registry import Collector
from sqlalchemy.pool import QueuePool

from shosai.core.db.engines import HomeDatabases
from shosai.core.kernel.homes import Home

type UnavailableReason = Literal["pool_timeout", "connect_failed", "unverified"]
type HomeStateName = Literal["unverified", "verified", "unreachable", "wrong_home", "behind"]
HOME_STATES: tuple[HomeStateName, ...] = (
    "unverified",
    "verified",
    "unreachable",
    "wrong_home",
    "behind",
)


class DatabaseMetrics:
    """Refused transactions and the check state of every home."""

    def __init__(self, registry: CollectorRegistry) -> None:
        self._unavailable = Counter(
            "shosai_db_unavailable",
            "Транзакции, не получившие соединение с базой дома",
            ("home", "reason"),
            registry=registry,
        )
        self._home_state = Enum(
            "shosai_db_home_state",
            "Результат проверки базы дома: чей это дом и подходит ли схема коду",
            ("home",),
            states=list(HOME_STATES),
            registry=registry,
        )
        for home in Home:
            self._home_state.labels(home=home.value).state("unverified")

    def count_unavailable(self, home: Home, reason: UnavailableReason) -> None:
        """Count one transaction refused for the home."""
        self._unavailable.labels(home=home.value, reason=reason).inc()

    def record_home_state(self, home: Home, state: HomeStateName) -> None:
        """Report the latest check result of a home."""
        self._home_state.labels(home=home.value).state(state)


class PoolOccupancy(Collector):
    """Connections in use and idle, and the pool size, per home at scrape time."""

    def __init__(self, databases: HomeDatabases) -> None:
        self._databases = databases

    def collect(self) -> Iterator[Metric]:
        """Read every home's pool once per scrape."""
        connections = GaugeMetricFamily(
            "shosai_db_pool_connections",
            "Соединения пула базы дома: занятые и свободные",
            labels=("home", "state"),
        )
        capacity = GaugeMetricFamily(
            "shosai_db_pool_capacity",
            "Размер пула базы дома в процессе",
            labels=("home",),
        )
        for home in Home:
            pool = self._databases.engine(home).pool
            if not isinstance(pool, QueuePool):
                continue
            connections.add_metric((home.value, "in_use"), pool.checkedout())
            connections.add_metric((home.value, "idle"), pool.checkedin())
            capacity.add_metric((home.value,), pool.size())
        yield connections
        yield capacity


def register_pool_occupancy(registry: CollectorRegistry, databases: HomeDatabases) -> None:
    """Report the pools of the process's databases in its registry."""
    registry.register(PoolOccupancy(databases))
