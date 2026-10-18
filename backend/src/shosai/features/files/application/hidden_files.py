"""Deleted files after their 7 hidden days: the purge (FL-D5).

Support's list and restore within the 7 days are in `support_files.py`. After 7 days the
purge removes the row, and the object when no row of any owner names its key; the sweep
role only lists what is due, each row goes in its owner's transaction.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Final
from uuid import UUID

import structlog
from sqlalchemy import delete, select

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.files.application.account_data import unnamed
from shosai.features.files.domain.quota import HIDDEN_FOR
from shosai.features.files.infrastructure.file_records import StorageFileRecord
from shosai.features.files.infrastructure.object_deleter import ObjectDeleter, record_deletions

# Строк за один проход очистки.
BATCH: Final = 500

log = structlog.stdlib.get_logger(__name__)


class HiddenFiles:
    """The purge of files hidden for more than 7 days."""

    def __init__(
        self,
        transactions: HomeTransactions,
        deleter: ObjectDeleter,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._deleter = deleter
        self._clock = clock

    async def purge(self, home: Home) -> int:
        """Remove files hidden for more than 7 days; how many went."""
        due = (
            select(StorageFileRecord.id, StorageFileRecord.user_id, StorageFileRecord.org_id)
            .where(StorageFileRecord.deleted_at <= self._clock() - HIDDEN_FOR)
            .limit(BATCH)
        )
        async with self._transactions.begin(
            TenancyScope(home), read_only=True, sweep=True
        ) as session:
            rows = (await session.execute(due)).all()
        for file_id, user_id, org_id in rows:
            await self._purge_one(TenancyScope(home, user_id, org_id), file_id)
        if rows:
            log.info("Скрытые файлы удалены окончательно", home=home.value, files=len(rows))
        return len(rows)

    async def _purge_one(self, scope: TenancyScope, file_id: UUID) -> None:
        async with self._transactions.begin(scope) as session:
            key = await session.scalar(
                delete(StorageFileRecord)
                .where(StorageFileRecord.id == file_id, StorageFileRecord.deleted_at.is_not(None))
                .returning(StorageFileRecord.object_key)
            )
            orphaned = [] if key is None else await unnamed(session, [key])
            await record_deletions(session, orphaned)
        await self._deleter.discard(scope.home, orphaned)
