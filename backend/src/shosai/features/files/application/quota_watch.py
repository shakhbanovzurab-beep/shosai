"""FL-D2 for one person: the mark over the limit, the reminders and the removal after 90 days.

The limit comes from billing's `Entitlements` before the owner's transaction; under the
row's lock the step is decided again, so a concurrent change never applies twice. Over the
limit, uploads and copies are refused by the reservation itself and everything else stays
available. A reminder is counted and its mail written in one transaction, so each goes
once. On day 90 the newest files over the limit take the ordinary deletion (FL-D5).
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.email.messages import EmailKind, OutgoingEmail
from shosai.core.email.port import EmailPort
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.billing.contracts import ENTITLEMENTS
from shosai.features.files.application.deletion import hide_file
from shosai.features.files.domain.quota import (
    OverLimitMark,
    QuotaAction,
    StoredFile,
    Usage,
    limit_bytes,
    newest_over_limit,
    quota_action,
    removal_date,
)
from shosai.features.files.emails.storage_over_limit import STORAGE_OVER_LIMIT_KEY
from shosai.features.files.infrastructure.file_records import StorageFileRecord
from shosai.features.files.infrastructure.quota_metrics import QuotaMetrics
from shosai.features.files.infrastructure.upload_records import StorageUsageRecord
from shosai.features.identity.contracts import ACCOUNT_PROFILE_READER

log = structlog.stdlib.get_logger(__name__)
# Шаги, которые не ждут ежедневного прохода: смена тарифа и восстановление файла.
MARKING = frozenset({QuotaAction.MARK, QuotaAction.CLEAR})


@dataclass(frozen=True, slots=True)
class QuotaStanding:
    """A person's storage as the File Manager's meter and banner show it."""

    used_bytes: int
    limit_bytes: int | None
    over_limit_since: datetime | None
    removal_at: datetime | None


class QuotaWatch:
    """Decides and takes a person's quota step in their home."""

    def __init__(
        self,
        transactions: HomeTransactions,
        services: tuple[PortDirectory, EventOutbox, EmailPort, QuotaMetrics],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._ports, self._outbox, self._email, self._metrics = services
        self._clock = clock

    async def limit(self, home: Home, user_id: UUID) -> int | None:
        """The person's storage limit in bytes; raises when entitlements cannot be read."""
        snapshot = await self._ports.get(ENTITLEMENTS).snapshot(home, user_id)
        return limit_bytes(snapshot.limits.file_manager_gb)

    async def standing(self, home: Home, user_id: UUID) -> QuotaStanding:
        """What the person holds against what the plan allows."""
        limit = await self.limit(home, user_id)
        async with self._transactions.begin(TenancyScope(home, user_id), read_only=True) as session:
            row = await session.get(StorageUsageRecord, user_id)
        if row is None:
            return QuotaStanding(0, limit, None, None)
        since = row.over_limit_since
        removal = None if since is None else removal_date(since)
        return QuotaStanding(row.used_bytes, limit, since, removal)

    async def step(self, home: Home, user_id: UUID, limit: int | None) -> QuotaAction | None:
        """The daily pass: take whatever step is due, in the person's transaction."""
        async with self._transactions.begin(TenancyScope(home, user_id)) as session:
            return await self.apply(session, user_id, limit, frozenset(QuotaAction))

    async def apply(
        self,
        session: AsyncSession,
        user_id: UUID,
        limit: int | None,
        allowed: frozenset[QuotaAction] = MARKING,
    ) -> QuotaAction | None:
        """Take the due step among `allowed` in the caller's transaction of the person."""
        row = await session.get(StorageUsageRecord, user_id, with_for_update=True)
        if row is None:
            return None
        now = self._clock()
        usage = Usage(row.used_bytes, row.reserved_bytes)
        action = quota_action(
            usage, limit, OverLimitMark(row.over_limit_since, row.reminders_sent), now
        )
        if action is None or action not in allowed:
            return None
        if action is QuotaAction.MARK:
            row.over_limit_since = now
        elif action is QuotaAction.CLEAR:
            row.over_limit_since, row.reminders_sent = None, 0
        elif action is QuotaAction.REMIND:
            await self._remind(session, row)
        elif limit is not None and await self._remove(session, row, limit, now):
            row.over_limit_since, row.reminders_sent = None, 0
        self._metrics.acted(action)
        log.info("Шаг квоты", user_id=str(user_id), action=action.value)
        return action

    async def _remind(self, session: AsyncSession, row: StorageUsageRecord) -> None:
        since = row.over_limit_since
        if since is None:
            return
        row.reminders_sent += 1
        profile = await self._ports.get(ACCOUNT_PROFILE_READER).profile(session, row.user_id)
        if profile is None or profile.email is None:
            log.warning("Напоминание квоты некуда отправить", user_id=str(row.user_id))
            return
        await self._email.enqueue(
            session,
            OutgoingEmail(
                recipient=profile.email, kind=EmailKind.ACCOUNT, template=STORAGE_OVER_LIMIT_KEY,
                locale=profile.language, user_id=row.user_id,
                params={"date": removal_date(since).date().isoformat()},
            ),
        )  # fmt: skip

    async def _remove(
        self, session: AsyncSession, row: StorageUsageRecord, limit: int, now: datetime
    ) -> bool:
        """Hide the newest files over the limit; whether what stays fits."""
        records = {
            record.id: record
            for record in await session.scalars(
                select(StorageFileRecord)
                .where(
                    StorageFileRecord.user_id == row.user_id,
                    StorageFileRecord.org_id.is_(None),
                    StorageFileRecord.deleted_at.is_(None),
                )
                .with_for_update()
            )
        }
        stored = [StoredFile(r.id, r.size_bytes, r.created_at) for r in records.values()]
        # UPDATE счётчика при скрытии делает поле строки устаревшим: значение берётся до него.
        used = row.used_bytes
        chosen = newest_over_limit(stored, used, limit)
        for file_id in chosen:
            await hide_file(session, self._outbox, records[file_id], now)
        left = used - sum(records[file_id].size_bytes for file_id in chosen)
        log.info("Файлы сверх лимита удалены", user_id=str(row.user_id), files=len(chosen))
        return left <= limit
