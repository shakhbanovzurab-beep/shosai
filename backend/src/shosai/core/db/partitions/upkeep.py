"""The partition upkeep of a home: each registered table keeps its window of months (§8.2).

One tick per home and day runs `maintain_monthly_partitions` for every table in
`partition_policies`, each in its own transaction, so one table's lock or failure never
holds back the others. It creates the partitions due ahead, drops the expired ones and
reports how far ahead the table can take rows: `shosai_partition_coverage_seconds` below
a month pages long before an insert could find no partition (§16.4).
"""

from dataclasses import dataclass
from datetime import datetime

import structlog
from prometheus_client import CollectorRegistry, Counter, Gauge
from sqlalchemy import func, select

from shosai.core.db.partitions.policy import maintain
from shosai.core.db.partitions.records import PartitionPolicy
from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope

log = structlog.stdlib.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class TableUpkeep:
    """What one table's upkeep did and how far ahead it is covered."""

    table: str
    created: tuple[str, ...]
    dropped: tuple[str, ...]
    deferred: tuple[str, ...]
    covered_until: datetime | None


class PartitionMetrics:
    """Partitions created and dropped, and the coverage ahead, per home and table."""

    def __init__(self, registry: CollectorRegistry) -> None:
        labels = ("home", "table")
        self._created = Counter(
            "shosai_partitions_created", "Созданные помесячные партиции", labels, registry=registry
        )
        self._dropped = Counter(
            "shosai_partitions_dropped",
            "Помесячные партиции, удалённые по сроку хранения",
            labels,
            registry=registry,
        )
        self._coverage = Gauge(
            "shosai_partition_coverage_seconds",
            "Сколько секунд вперёд таблица принимает строки: до конца последней партиции",
            labels,
            registry=registry,
        )

    def record(self, home: Home, upkeep: TableUpkeep, coverage_seconds: float) -> None:
        """One table's upkeep in a home."""
        labels = {"home": home.value, "table": upkeep.table}
        self._created.labels(**labels).inc(len(upkeep.created))
        self._dropped.labels(**labels).inc(len(upkeep.dropped))
        self._coverage.labels(**labels).set(coverage_seconds)


class PartitionUpkeep:
    """Keeps the partitions of every registered table of a home."""

    def __init__(self, transactions: HomeTransactions, metrics: PartitionMetrics) -> None:
        self._transactions = transactions
        self._metrics = metrics

    async def maintain(self, home: Home) -> list[TableUpkeep]:
        """Run the upkeep of each registered table of the home, one transaction each."""
        scope = TenancyScope(home)
        async with self._transactions.begin(scope, read_only=True) as session:
            tables = (await session.scalars(select(PartitionPolicy.table_name))).all()
        results = []
        for table in sorted(tables):
            async with self._transactions.begin(scope) as session:
                row = (await session.execute(maintain(table))).one()
                now = (await session.execute(select(func.now()))).scalar_one()
            upkeep = TableUpkeep(
                table=table,
                created=tuple(row.created),
                dropped=tuple(row.dropped),
                deferred=tuple(row.deferred),
                covered_until=row.covered_until,
            )
            covered = upkeep.covered_until
            self._metrics.record(home, upkeep, (covered - now).total_seconds() if covered else 0)
            if upkeep.created or upkeep.dropped or upkeep.deferred:
                log.info(
                    "Помесячные партиции обновлены",
                    home=home.value,
                    table=table,
                    created=list(upkeep.created),
                    dropped=list(upkeep.dropped),
                    deferred=list(upkeep.deferred),
                )
            results.append(upkeep)
        return results
