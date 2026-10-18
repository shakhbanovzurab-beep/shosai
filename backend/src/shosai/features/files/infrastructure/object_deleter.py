"""Objects deleted after the commit that removed their last pointer (ADR 0055 point 7).

The caller records each key in `object_deletions` in its own transaction; after the commit
`discard` deletes the objects and their records. A key the bucket did not delete stays
recorded, and the sweep retries it until the bucket confirms, so no object is lost track of.
"""

from collections.abc import Mapping, Sequence

import structlog
from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.storage.errors import ObjectsNotDeletedError, StorageUnavailableError
from shosai.core.storage.port import ObjectStorage
from shosai.features.files.infrastructure.upload_records import ObjectDeletionRecord

# Ключей за один проход очистки.
BATCH = 500

log = structlog.stdlib.get_logger(__name__)


async def record_deletions(session: AsyncSession, keys: Sequence[str]) -> None:
    """Note the keys to delete, in the transaction that removed their last pointer."""
    if keys:
        await session.execute(
            insert(ObjectDeletionRecord)
            .values([{"object_key": key} for key in keys])
            .on_conflict_do_nothing(index_elements=[ObjectDeletionRecord.object_key])
        )


class ObjectDeleter:
    """Deletes recorded objects from a home's bucket and forgets the confirmed ones."""

    def __init__(
        self, transactions: HomeTransactions, objects: Mapping[Home, ObjectStorage]
    ) -> None:
        self._transactions = transactions
        self._objects = objects

    async def discard(self, home: Home, keys: Sequence[str]) -> None:
        """After the commit: delete the objects; what failed waits for the sweep."""
        if not keys:
            return
        failed: set[str] = set()
        try:
            await self._objects[home].delete_many(keys)
        except ObjectsNotDeletedError as error:
            failed = set(error.keys)
        except StorageUnavailableError:
            log.warning("Объекты не удалены: бакет недоступен, повторит очистка", home=home.value)
            await self._count_attempt(home, keys)
            return
        done = [key for key in keys if key not in failed]
        async with self._transactions.begin(TenancyScope(home)) as session:
            if done:
                await session.execute(
                    delete(ObjectDeletionRecord).where(ObjectDeletionRecord.object_key.in_(done))
                )
        if failed:
            await self._count_attempt(home, sorted(failed))

    async def retry(self, home: Home) -> int:
        """The sweep's pass over recorded keys; how many it handled."""
        async with self._transactions.begin(TenancyScope(home), read_only=True) as session:
            keys = list(
                await session.scalars(
                    select(ObjectDeletionRecord.object_key)
                    .order_by(ObjectDeletionRecord.created_at)
                    .limit(BATCH)
                )
            )
        await self.discard(home, keys)
        return len(keys)

    async def _count_attempt(self, home: Home, keys: Sequence[str]) -> None:
        async with self._transactions.begin(TenancyScope(home)) as session:
            await session.execute(
                update(ObjectDeletionRecord)
                .where(ObjectDeletionRecord.object_key.in_(keys))
                .values(attempts=ObjectDeletionRecord.attempts + 1)
            )
