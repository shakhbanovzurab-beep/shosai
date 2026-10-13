"""Removal of expired effect keys, home by home, in batches (F1 audit A9).

A key outlives every repeat of its effect by the `keep` of its scope; after that nothing
can repeat it, and the row only takes space. Keys go in batches of 5 000, each in its own
transaction, so the purge holds no long lock and no large transaction.
"""

from typing import Final

import structlog
from sqlalchemy import delete, func, select, tuple_

from shosai.core.db.transactions import HomeTransactions
from shosai.core.idempotency.metrics import EffectKeyMetrics
from shosai.core.idempotency.records import EffectKeyRecord
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope

PURGE_BATCH: Final = 5_000
log = structlog.stdlib.get_logger(__name__)


class EffectKeyPurge:
    """Removes the expired keys of a home."""

    def __init__(
        self, transactions: HomeTransactions, metrics: EffectKeyMetrics, batch: int = PURGE_BATCH
    ) -> None:
        self._transactions = transactions
        self._metrics = metrics
        self._batch = batch

    async def purge(self, home: Home) -> int:
        """Remove every expired key of the home, batch by batch; return how many."""
        expired = (
            select(EffectKeyRecord.scope, EffectKeyRecord.key)
            .where(EffectKeyRecord.expires_at <= func.now())
            .limit(self._batch)
        )
        statement = delete(EffectKeyRecord).where(
            tuple_(EffectKeyRecord.scope, EffectKeyRecord.key).in_(expired)
        )
        removed = 0
        while True:
            async with self._transactions.begin(TenancyScope(home)) as session:
                # Через соединение: оператор ядра, и известно число удалённых строк.
                connection = await session.connection()
                count = (await connection.execute(statement)).rowcount
            removed += count
            if count:
                self._metrics.count_purged(home, count)
            if count < self._batch:
                log.info("Удалены истёкшие ключи эффектов", home=home.value, removed=removed)
                return removed
