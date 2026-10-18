"""The daily quota pass per home (FL-D2): lapses and plan edits reach every person.

A lapse or an edit of a plan in the catalogue changes no row of files, so once a day the
sweep role lists the people who hold bytes or carry a mark, a page at a time; each one's
limit comes from `Entitlements`, and only a person with a step due opens a transaction,
where the step is decided again under the lock. A person whose entitlements cannot be read
is left for the next day and counted in the log.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Final
from uuid import UUID

import structlog
from sqlalchemy import or_, select

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.billing.contracts import EntitlementsUnavailableError
from shosai.features.files.application.quota_watch import QuotaWatch
from shosai.features.files.domain.quota import OverLimitMark, Usage, quota_action
from shosai.features.files.infrastructure.upload_records import StorageUsageRecord

# Людей за одну страницу прохода.
PAGE: Final = 500
log = structlog.stdlib.get_logger(__name__)
USAGE = StorageUsageRecord


class QuotaSweep:
    """Walks a home's usage rows and takes each person's due step."""

    def __init__(
        self,
        transactions: HomeTransactions,
        watch: QuotaWatch,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._watch = watch
        self._clock = clock

    async def run(self, home: Home) -> int:
        """One pass over the home; how many steps were taken."""
        taken = unread = 0
        after: UUID | None = None
        while True:
            rows = await self._page(home, after)
            for row in rows:
                try:
                    limit = await self._watch.limit(home, row.user_id)
                except EntitlementsUnavailableError:
                    unread += 1
                    continue
                usage = Usage(row.used_bytes, row.reserved_bytes)
                mark = OverLimitMark(row.over_limit_since, row.reminders_sent)
                if quota_action(usage, limit, mark, self._clock()) is None:
                    continue
                if await self._watch.step(home, row.user_id, limit) is not None:
                    taken += 1
            if len(rows) < PAGE:
                break
            after = rows[-1].user_id
        if unread:
            log.warning("Квота не проверена: тариф не прочитан", home=home.value, people=unread)
        return taken

    async def _page(self, home: Home, after: UUID | None) -> list[StorageUsageRecord]:
        query = select(USAGE).where(
            or_(USAGE.used_bytes > 0, USAGE.over_limit_since.is_not(None)),
            USAGE.account_hidden.is_(False),
        )
        if after is not None:
            query = query.where(USAGE.user_id > after)
        query = query.order_by(USAGE.user_id).limit(PAGE)
        async with self._transactions.begin(
            TenancyScope(home), read_only=True, sweep=True
        ) as session:
            rows = list(await session.scalars(query))
            session.expunge_all()
        return rows
