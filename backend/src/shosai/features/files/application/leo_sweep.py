"""The daily pass over the knowledge limit per home (FL-D10): lapses reach every person.

A lapse or an edit of a plan changes no row of files, so once a day the sweep role lists
the people who hold bytes or carry Leo's mark, a page at a time, with the files Leo uses
for the whole page in one query. Only a person whom Leo reads for, or who carries the mark,
has their limit read; only one with a step due opens a transaction, where the step is
decided again under the person's locks. A person whose entitlements cannot be read is
left for the next day and counted in the log.
"""

from collections import defaultdict
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
from shosai.features.files.application.leo_use import in_use_rows, rows_of
from shosai.features.files.application.leo_watch import LeoWatch
from shosai.features.files.domain.leo import LeoCandidate, bytes_in_use
from shosai.features.files.domain.quota import OverLimitMark, Usage, quota_action
from shosai.features.files.infrastructure.file_records import StorageFileRecord
from shosai.features.files.infrastructure.upload_records import StorageUsageRecord

# Людей за одну страницу прохода.
PAGE: Final = 500
log = structlog.stdlib.get_logger(__name__)
USAGE = StorageUsageRecord


class LeoSweep:
    """Walks a home's usage rows and takes each person's due FL-D10 step."""

    def __init__(
        self,
        transactions: HomeTransactions,
        watch: LeoWatch,
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
            rows, in_use = await self._page(home, after)
            for row in rows:
                used = in_use.get(row.user_id, 0)
                if used == 0 and row.leo_over_limit_since is None:
                    continue
                try:
                    limit = await self._watch.limit(home, row.user_id)
                except EntitlementsUnavailableError:
                    unread += 1
                    continue
                mark = OverLimitMark(row.leo_over_limit_since, row.leo_reminders_sent)
                if quota_action(Usage(used, 0), limit, mark, self._clock()) is None:
                    continue
                if await self._watch.step(home, row.user_id, limit) is not None:
                    taken += 1
            if len(rows) < PAGE:
                break
            after = rows[-1].user_id
        if unread:
            log.warning(
                "Лимит знаний не проверен: тариф не прочитан", home=home.value, people=unread
            )
        return taken

    async def _page(
        self, home: Home, after: UUID | None
    ) -> tuple[list[StorageUsageRecord], dict[UUID, int]]:
        """A page of usage rows and the bytes Leo uses for each of their people."""
        query = select(USAGE).where(
            or_(USAGE.used_bytes > 0, USAGE.leo_over_limit_since.is_not(None)),
            USAGE.account_hidden.is_(False),
        )
        if after is not None:
            query = query.where(USAGE.user_id > after)
        query = query.order_by(USAGE.user_id).limit(PAGE)
        async with self._transactions.begin(
            TenancyScope(home), read_only=True, sweep=True
        ) as session:
            rows = list(await session.scalars(query))
            people = [row.user_id for row in rows]
            files = in_use_rows(
                select(StorageFileRecord).where(StorageFileRecord.user_id.in_(people))
            )
            found = rows_of(await session.execute(files)) if people else []
            session.expunge_all()
        by_person: dict[UUID, list[LeoCandidate]] = defaultdict(list)
        for user_id, candidate in found:
            by_person[user_id].append(candidate)
        return rows, {user_id: bytes_in_use(files) for user_id, files in by_person.items()}
