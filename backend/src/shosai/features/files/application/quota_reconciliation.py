"""inv-11's daily reconciliation per home: counters against files, objects against rows.

The sweep role compares each person's `used_bytes` with the sum of their visible personal
files and of the objects files holds for them (ADR 0064) in one statement, so a claim or a
deletion never shows half done. The home's bucket is then listed under the v2 prefixes a
page at a time, outside any transaction; an object older than a day (uploads expire within
24 hours) whose key no file row or held object names and no deletion waits for is an
orphan. Both counts become the monitors' gauges and are logged with the first ids; nothing
is fixed silently. A home or bucket out of reach keeps its gauge.
"""

from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Final
from uuid import UUID

import structlog
from sqlalchemy import select, text

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.storage.port import ObjectStorage
from shosai.features.files.application.account_data import unnamed
from shosai.features.files.infrastructure.quota_metrics import QuotaMetrics
from shosai.features.files.infrastructure.upload_records import ObjectDeletionRecord

# Объект моложе суток с часом запаса может принадлежать идущей загрузке.
ORPHAN_AGE: Final = timedelta(hours=25)
PREFIXES: Final = ("u/", "o/")
BATCH: Final = 1000
LOGGED_IDS: Final = 20
# Место человека — его видимые личные файлы и объекты, которые files держит для других
# срезов (ADR 0064).
DRIFT_SQL: Final = text(
    "SELECT coalesce(u.user_id, f.user_id) FROM storage_usage u FULL JOIN ("
    " SELECT user_id, sum(size_bytes) AS total FROM ("
    " SELECT user_id, size_bytes FROM storage_files WHERE org_id IS NULL AND deleted_at IS NULL"
    " UNION ALL SELECT user_id, size_bytes FROM held_objects WHERE org_id IS NULL"
    ") counted GROUP BY user_id"
    ") f ON f.user_id = u.user_id"
    " WHERE coalesce(u.used_bytes, 0) <> coalesce(f.total, 0)"
)
log = structlog.stdlib.get_logger(__name__)


class QuotaReconciliation:
    """Counts drifted counters and orphaned objects of a home and reports them."""

    def __init__(
        self,
        transactions: HomeTransactions,
        storage: tuple[Mapping[Home, ObjectStorage], QuotaMetrics],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._objects, self._metrics = storage
        self._clock = clock

    async def run(self, home: Home) -> tuple[int, int]:
        """The drifted owners and the orphaned objects of the home."""
        drifted = await self._drifted(home)
        self._metrics.drift(home, len(drifted))
        if drifted:
            log.error(
                "Счётчик места расходится с файлами", home=home.value, owners=len(drifted),
                user_ids=[str(user_id) for user_id in drifted[:LOGGED_IDS]],
            )  # fmt: skip
        orphans = await self._orphans(home)
        self._metrics.orphans(home, orphans)
        if orphans:
            log.error("В бакете есть объекты без строки", home=home.value, objects=orphans)
        return len(drifted), orphans

    async def _drifted(self, home: Home) -> list[UUID]:
        async with self._transactions.begin(
            TenancyScope(home), read_only=True, sweep=True
        ) as session:
            return list(await session.scalars(DRIFT_SQL))

    async def _orphans(self, home: Home) -> int:
        cutoff = self._clock() - ORPHAN_AGE
        found = 0
        for prefix in PREFIXES:
            batch: list[str] = []
            async for info in self._objects[home].list_objects(prefix):
                if info.last_modified < cutoff:
                    batch.append(info.key)
                if len(batch) == BATCH:
                    found += await self._unnamed(home, batch)
                    batch = []
            found += await self._unnamed(home, batch)
        return found

    async def _unnamed(self, home: Home, keys: Sequence[str]) -> int:
        """How many of the keys no row names and no deletion waits for."""
        if not keys:
            return 0
        async with self._transactions.begin(TenancyScope(home), read_only=True) as session:
            free = await unnamed(session, keys)
            waiting = set(
                await session.scalars(
                    select(ObjectDeletionRecord.object_key).where(
                        ObjectDeletionRecord.object_key.in_(free)
                    )
                )
            )
        return len([key for key in free if key not in waiting])
