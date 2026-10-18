"""FL-D10 for one person: Leo's mark over the knowledge limit, the reminders and day 90.

The limit comes from billing's `Entitlements` before the transaction. Inside it the caller
holds the person's Leo lock; the usage row is locked next and the step is decided again
from the bytes Leo uses now, so a concurrent change never applies twice and the person's
locks keep their one order. Over the limit only new use is refused and Leo keeps reading
everything. A reminder is counted and its mail written in one transaction, so each goes
once. On day 90 Leo stops using the newest files over the limit — their own switch off, a
file of a folder Leo reads held — until the rest fits; no file is deleted.
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
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.billing.contracts import ENTITLEMENTS
from shosai.features.files.application.leo_use import LeoUse
from shosai.features.files.domain.leo import LeoCandidate, LeoShift, bytes_in_use, knowledge_limit
from shosai.features.files.domain.quota import (
    OverLimitMark,
    QuotaAction,
    StoredFile,
    Usage,
    newest_over_limit,
    quota_action,
    removal_date,
)
from shosai.features.files.emails.leo_over_limit import LEO_OVER_LIMIT_KEY
from shosai.features.files.infrastructure.file_records import StorageFileRecord
from shosai.features.files.infrastructure.quota_metrics import QuotaMetrics
from shosai.features.files.infrastructure.upload_records import StorageUsageRecord
from shosai.features.identity.contracts import ACCOUNT_PROFILE_READER

log = structlog.stdlib.get_logger(__name__)
# Шаги, которые не ждут ежедневного прохода: смена тарифа и восстановление файла.
MARKING = frozenset({QuotaAction.MARK, QuotaAction.CLEAR})


@dataclass(frozen=True, slots=True)
class LeoStanding:
    """What Leo uses against the plan's knowledge limit, for the meter and the banner."""

    used_bytes: int
    limit_bytes: int | None
    over_limit_since: datetime | None
    removal_at: datetime | None


class LeoWatch:
    """Decides and takes a person's FL-D10 step in their home."""

    def __init__(
        self,
        transactions: HomeTransactions,
        services: tuple[PortDirectory, LeoUse, EmailPort, QuotaMetrics],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._ports, self._leo, self._email, self._metrics = services
        self._clock = clock

    async def limit(self, home: Home, user_id: UUID) -> int | None:
        """The person's knowledge limit in bytes; raises when entitlements cannot be read."""
        snapshot = await self._ports.get(ENTITLEMENTS).snapshot(home, user_id)
        return knowledge_limit(snapshot.limits.knowledge_base_mb)

    async def standing(self, home: Home, user_id: UUID) -> LeoStanding:
        """The bytes Leo uses, the limit and, over it, since when and until when."""
        limit = await self.limit(home, user_id)
        async with self._transactions.begin(TenancyScope(home, user_id), read_only=True) as session:
            row = await session.get(StorageUsageRecord, user_id)
            used = bytes_in_use(await self._leo.in_use(session, user_id))
        since = None if row is None else row.leo_over_limit_since
        return LeoStanding(used, limit, since, None if since is None else removal_date(since))

    async def step(self, home: Home, user_id: UUID, limit: int | None) -> QuotaAction | None:
        """The daily pass: take whatever step is due, in the person's transaction."""
        async with self._transactions.begin(TenancyScope(home, user_id)) as session:
            await self._leo.hold(session, user_id)
            return await self.apply(session, user_id, limit, frozenset(QuotaAction))

    async def follow(
        self, session: AsyncSession, user_id: UUID, limit: int | None
    ) -> QuotaAction | None:
        """Mark or clear at once, in a transaction that has taken no lock of the person yet."""
        await self._leo.hold(session, user_id)
        return await self.apply(session, user_id, limit)

    async def apply(
        self,
        session: AsyncSession,
        user_id: UUID,
        limit: int | None,
        allowed: frozenset[QuotaAction] = MARKING,
    ) -> QuotaAction | None:
        """Take the due step among `allowed`; the caller holds the person's Leo lock."""
        row = await session.get(StorageUsageRecord, user_id, with_for_update=True)
        if row is None:
            return None
        now = self._clock()
        in_use = [file for file in await self._leo.in_use(session, user_id) if file.used]
        mark = OverLimitMark(row.leo_over_limit_since, row.leo_reminders_sent)
        action = quota_action(Usage(bytes_in_use(in_use), 0), limit, mark, now)
        if action is None or action not in allowed:
            return None
        if action is QuotaAction.MARK:
            row.leo_over_limit_since = now
        elif action is QuotaAction.CLEAR:
            row.leo_over_limit_since, row.leo_reminders_sent = None, 0
        elif action is QuotaAction.REMIND:
            await self._remind(session, row)
        elif limit is not None and await self._release(session, user_id, in_use, limit):
            row.leo_over_limit_since, row.leo_reminders_sent = None, 0
        self._metrics.leo_acted(action)
        log.info("Шаг лимита знаний", user_id=str(user_id), action=action.value)
        return action

    async def _remind(self, session: AsyncSession, row: StorageUsageRecord) -> None:
        since = row.leo_over_limit_since
        if since is None:
            return
        row.leo_reminders_sent += 1
        profile = await self._ports.get(ACCOUNT_PROFILE_READER).profile(session, row.user_id)
        if profile is None or profile.email is None:
            log.warning("Напоминание о лимите знаний некуда отправить", user_id=str(row.user_id))
            return
        await self._email.enqueue(
            session,
            OutgoingEmail(
                recipient=profile.email, kind=EmailKind.ACCOUNT, template=LEO_OVER_LIMIT_KEY,
                locale=profile.language, user_id=row.user_id,
                params={"date": removal_date(since).date().isoformat()},
            ),
        )  # fmt: skip

    async def _release(
        self, session: AsyncSession, user_id: UUID, in_use: list[LeoCandidate], limit: int
    ) -> bool:
        """Stop Leo using the newest files over the limit; whether what stays fits."""
        through_folder = {file.file_id: file.folder for file in in_use}
        records = {
            record.id: record
            for record in await session.scalars(
                select(StorageFileRecord)
                .where(StorageFileRecord.id.in_(list(through_folder)))
                .with_for_update()
            )
        }
        used = bytes_in_use(in_use)
        stored = [StoredFile(r.id, r.size_bytes, r.created_at) for r in records.values()]
        chosen = newest_over_limit(stored, used, limit)
        for file_id in chosen:
            records[file_id].leo_on = False
            records[file_id].leo_held = through_folder[file_id]
        await session.flush()
        await self._leo.settle(session, user_id, LeoShift(stopped=frozenset(chosen)), None)
        log.info(
            "Файлы сверх лимита знаний выключены из Leo", user_id=str(user_id), files=len(chosen)
        )
        return used - sum(records[file_id].size_bytes for file_id in chosen) <= limit
