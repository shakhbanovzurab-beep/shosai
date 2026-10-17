"""The `Entitlements` port: a person's snapshot from Valkey, or from the database on a miss.

A cached entry is read only while it is in time, of the current catalogue mark and not
older than the subscription's version. On a miss the subscription is read in the
person's home and the catalogue in the EU, at once; an outage of either is
`EntitlementsUnavailableError` (503), never a guessed plan (inv-3). Valkey out of
reach only costs the database read.
"""

import asyncio
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Final, Protocol
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from shosai.core.db.errors import HomeUnavailableError
from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.billing.application.catalogue import CATALOGUE_SCOPE
from shosai.features.billing.application.entitlement_build import (
    QueuedRow,
    SubscriptionRow,
    UnknownPlanError,
    build_entry,
)
from shosai.features.billing.application.entitlement_entries import EntitlementEntry
from shosai.features.billing.contracts import EntitlementSnapshot, EntitlementsUnavailableError
from shosai.features.billing.domain.plans import BillingPeriod, Plan
from shosai.features.billing.infrastructure.catalogue_rows import plan_of
from shosai.features.billing.infrastructure.plan_records import TariffRecord
from shosai.features.billing.infrastructure.subscription_records import (
    SubscriptionRecord,
    SubscriptionSegmentRecord,
)

# Сбой базы, недоступный дом и оборванное соединение значат одно: права неизвестны.
OUTAGES: Final = (SQLAlchemyError, HomeUnavailableError, OSError, TimeoutError)

log = structlog.stdlib.get_logger(__name__)


class CachedReading(Protocol):
    """What the store holds for a person."""

    @property
    def entry(self) -> EntitlementEntry | None:
        """The stored entry, if any."""
        ...

    @property
    def catalogue(self) -> str | None:
        """The current catalogue mark, if the store answered."""
        ...


class EntitlementStore(Protocol):
    """Where entries are kept between reads."""

    async def read(self, user_id: UUID) -> CachedReading:
        """The person's entry and the catalogue mark."""
        ...

    async def catalogue_mark(self, known: str | None) -> str | None:
        """The current catalogue mark, created when missing."""
        ...

    async def store(self, entry: EntitlementEntry, now: datetime) -> bool:
        """Keep an entry unless a newer one or another catalogue came first."""
        ...


class EntitlementSnapshots:
    """Builds and caches the person's entitlement entry."""

    def __init__(
        self,
        transactions: HomeTransactions,
        store: EntitlementStore,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._store = store
        self._clock = clock

    async def snapshot(self, home: Home, user_id: UUID) -> EntitlementSnapshot:
        """The person's snapshot; `EntitlementsUnavailableError` when it cannot be read."""
        return (await self.entry(home, user_id)).snapshot

    async def entry(self, home: Home, user_id: UUID) -> EntitlementEntry:
        """The person's whole entry: the snapshot and the native card."""
        now = self._clock()
        reading = await self._store.read(user_id)
        cached = reading.entry
        if cached is not None and cached.fresh(now, reading.catalogue):
            return cached
        catalogue = await self._store.catalogue_mark(reading.catalogue)
        try:
            held, plans = await asyncio.gather(self._subscription(home, user_id), self._catalogue())
            entry = build_entry(user_id, held, plans, (now, catalogue or ""))
        except OUTAGES as error:
            log.warning("Права не прочитаны: база недоступна", home=home.value)
            raise EntitlementsUnavailableError from error
        except UnknownPlanError as error:
            log.error("Подписка ссылается на тариф вне каталога", home=home.value)
            raise EntitlementsUnavailableError from error
        await self._store.store(entry, now)
        return entry

    async def _subscription(
        self, home: Home, user_id: UUID
    ) -> tuple[SubscriptionRow | None, Sequence[QueuedRow]]:
        queue = (
            select(SubscriptionSegmentRecord.plan_id, SubscriptionSegmentRecord.remaining_days)
            .where(SubscriptionSegmentRecord.user_id == user_id)
            .order_by(SubscriptionSegmentRecord.position)
        )
        scope = TenancyScope(home, user_id)
        async with self._transactions.begin(scope, read_only=True) as session:
            record = await session.scalar(
                select(SubscriptionRecord).where(SubscriptionRecord.user_id == user_id)
            )
            queued = (await session.execute(queue)).all() if record is not None else []
        if record is None:
            return None, ()
        period = None if record.billing_period is None else BillingPeriod(record.billing_period)
        row = SubscriptionRow(
            plan_id=record.plan_id, billing_period=period, started_at=record.started_at,
            expires_at=record.expires_at, auto_renew=record.auto_renew, trial=record.trial,
            version=record.version,
        )  # fmt: skip
        return row, tuple(QueuedRow(item.plan_id, item.remaining_days) for item in queued)

    async def _catalogue(self) -> Mapping[UUID, Plan]:
        async with self._transactions.begin(CATALOGUE_SCOPE, read_only=True) as session:
            rows = (await session.scalars(select(TariffRecord))).all()
        return {row.id: plan_of(row) for row in rows}
