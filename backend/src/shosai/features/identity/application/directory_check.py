"""The inv-1 check: directory entries whose account is missing from their home (§16.4).

Every hour, from the EU, after the claim sweep has settled the claims older than 10
minutes: each entry not freed by an erasure and unchanged for 10 minutes is looked up in
its home, a page of the directory at a time. The count per home becomes the monitor's
gauge `shosai_identity_directory_orphans{home}`, zero while every address leads to an
account. The pass reads the whole directory, so it runs hourly rather than with the
5-minute sweep: an orphan comes only from a fault, and an hour is soon enough to page.
A home out of reach keeps its gauge as it was and says so in the log, since an unread
home must not read as a clean one.
"""

from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Final
from uuid import UUID

import structlog
from prometheus_client import CollectorRegistry, Gauge
from sqlalchemy import select

from shosai.core.db.errors import HomeUnavailableError
from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.identity.domain.registration import DirectoryState
from shosai.features.identity.infrastructure.records import DirectoryEntry, User

ORPHAN_AGE: Final = timedelta(minutes=10)
PAGE_ENTRIES: Final = 5000
# В строку журнала попадают первые id: их хватает, чтобы начать разбор.
LOGGED_IDS: Final = 20
log = structlog.stdlib.get_logger(__name__)

type Listed = tuple[bytes, UUID, Home]


class DirectoryCheck:
    """Counts the directory's entries without an account and sets the monitor's gauge."""

    def __init__(self, transactions: HomeTransactions, registry: CollectorRegistry) -> None:
        self._transactions = transactions
        self._orphans = Gauge(
            "shosai_identity_directory_orphans",
            "Записи каталога старше 10 минут, у которых нет аккаунта в их доме",
            ("home",),
            registry=registry,
        )

    async def run(self, now: datetime | None = None) -> Mapping[Home, int] | None:
        """The orphans per home that could be read; None when the directory could not."""
        cutoff = (now or datetime.now(UTC)) - ORPHAN_AGE
        orphans: dict[Home, list[UUID]] = {home: [] for home in Home}
        unread: set[Home] = set()
        after: bytes | None = None
        while True:
            try:
                page = await self._page(cutoff, after)
            except HomeUnavailableError:
                log.warning("Проверка каталога пропущена: дом ЕС недоступен")
                return None
            for home, user_ids in _by_home(page).items():
                if home not in unread:
                    missing = await self._missing(home, user_ids)
                    if missing is None:
                        unread.add(home)
                    else:
                        orphans[home].extend(missing)
            if len(page) < PAGE_ENTRIES:
                break
            after = page[-1][0]
        return self._report(orphans, unread)

    async def _page(self, cutoff: datetime, after: bytes | None) -> list[Listed]:
        query = select(DirectoryEntry.email_hmac, DirectoryEntry.user_id, DirectoryEntry.home)
        query = query.where(
            DirectoryEntry.state != DirectoryState.DELETED.value,
            DirectoryEntry.updated_at < cutoff,
        )
        if after is not None:
            query = query.where(DirectoryEntry.email_hmac > after)
        query = query.order_by(DirectoryEntry.email_hmac).limit(PAGE_ENTRIES)
        async with self._transactions.begin(TenancyScope(Home.EU), read_only=True) as session:
            rows = (await session.execute(query)).all()
        return [(row.email_hmac, row.user_id, Home(row.home)) for row in rows]

    async def _missing(self, home: Home, user_ids: Sequence[UUID]) -> list[UUID] | None:
        """The ids with no account in the home; None when the home does not answer."""
        try:
            async with self._transactions.begin(TenancyScope(home), read_only=True) as session:
                found = set(await session.scalars(select(User.id).where(User.id.in_(user_ids))))
        except HomeUnavailableError:
            log.warning("Проверка каталога не прочла дом", home=home.value)
            return None
        return [user_id for user_id in user_ids if user_id not in found]

    def _report(self, orphans: Mapping[Home, list[UUID]], unread: set[Home]) -> dict[Home, int]:
        counts: dict[Home, int] = {}
        for home, user_ids in orphans.items():
            if home in unread:
                continue
            counts[home] = len(user_ids)
            self._orphans.labels(home=home.value).set(len(user_ids))
            if user_ids:
                log.error(
                    "В каталоге есть адреса без аккаунта в их доме",
                    home=home.value,
                    count=len(user_ids),
                    user_ids=[str(user_id) for user_id in user_ids[:LOGGED_IDS]],
                )
        return counts


def _by_home(page: Sequence[Listed]) -> dict[Home, list[UUID]]:
    grouped: dict[Home, list[UUID]] = defaultdict(list)
    for _email_hmac, user_id, home in page:
        grouped[home].append(user_id)
    return grouped
