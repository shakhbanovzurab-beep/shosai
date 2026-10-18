"""Deleted files during their 7 hidden days: support's list and restore, then the purge (FL-D5).

Support reads a person's hidden files in the person's home and restores one: it comes back
into the quota (passing the limit starts the 90 days, FL-D2) and is shared nowhere. After
7 days the purge removes the row, and the object when no row of any owner names its key;
the sweep role only lists what is due, each row goes in its owner's transaction.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Final
from uuid import UUID

import structlog
from sqlalchemy import delete, select

from shosai.core.db.transactions import HomeTransactions
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.files.application.account_data import unnamed
from shosai.features.files.contracts.events import FileRestored
from shosai.features.files.domain.quota import HIDDEN_FOR
from shosai.features.files.infrastructure import usage_store
from shosai.features.files.infrastructure.file_records import StorageFileRecord
from shosai.features.files.infrastructure.object_deleter import ObjectDeleter, record_deletions

# Строк за один проход очистки.
BATCH: Final = 500

log = structlog.stdlib.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class HiddenFile:
    """A deleted file support may still bring back."""

    file_id: UUID
    name: str
    size_bytes: int
    deleted_at: datetime


class HiddenFiles:
    """Support's view of deleted files and the purge after 7 days."""

    def __init__(
        self,
        transactions: HomeTransactions,
        services: tuple[EventOutbox, ObjectDeleter],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._outbox, self._deleter = services
        self._clock = clock

    async def of_person(self, home: Home, user_id: UUID) -> list[HiddenFile]:
        """The person's hidden files, the latest deletion first."""
        query = (
            select(StorageFileRecord)
            .where(StorageFileRecord.user_id == user_id, StorageFileRecord.deleted_at.is_not(None))
            .order_by(StorageFileRecord.deleted_at.desc())
        )
        async with self._transactions.begin(TenancyScope(home, user_id), read_only=True) as session:
            rows = list(await session.scalars(query))
        return [HiddenFile(r.id, r.name, r.size_bytes, r.deleted_at) for r in rows if r.deleted_at]

    async def restore(self, home: Home, user_id: UUID, file_id: UUID) -> None:
        """Bring a hidden file back into the person's File Manager and quota."""
        async with self._transactions.begin(TenancyScope(home, user_id)) as session:
            record = await session.get(StorageFileRecord, file_id, with_for_update=True)
            if record is None or record.user_id != user_id or record.deleted_at is None:
                raise AppError("hidden_file_not_found", HTTPStatus.NOT_FOUND)
            record.deleted_at = None
            await usage_store.add_used(session, user_id, record.size_bytes)
            await self._outbox.add(
                session, FileRestored(file_id=file_id, user_id=user_id, org_id=record.org_id)
            )

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
