"""Subscriptions and cached entitlements over the slot's homes and Valkey.

Builds on the catalogue bench (the plan table is restored after each test) and adds the
ledger, the snapshots with a settable clock and a way to take the databases away.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID

import pytest_asyncio
from redis.asyncio import Redis

from shosai.core.db.errors import HomeUnavailableError
from shosai.core.db.transactions import HomeTransactions
from shosai.core.events.catalog import EventTypes
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.billing.application.entitlement_snapshots import EntitlementSnapshots
from shosai.features.billing.application.subscription_ledger import (
    PlanRef,
    SubscriptionLedger,
    SubscriptionTerms,
)
from shosai.features.billing.domain.plans import BillingPeriod
from shosai.features.billing.infrastructure.entitlement_cache import EntitlementCache
from shosai.features.billing.module import BILLING
from tests.features.billing.catalogue_bench import CatalogueBench
from tests.harness.database_access import DatabaseAccess


class HomesUnreachable:
    """Transactions of a database out of reach: every home refuses."""

    def begin(self, scope: TenancyScope, *, read_only: bool = False) -> object:
        """Refuse as an outage would."""
        del read_only
        raise HomeUnavailableError(scope.home)


@dataclass
class Clock:
    """A clock the test moves; it starts at the real time, as the composed app's clock does."""

    now: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __call__(self) -> datetime:
        return self.now

    def advance(self, by: timedelta) -> None:
        """Move time forward."""
        self.now += by


@dataclass(frozen=True, slots=True)
class EntitlementBench:
    """The ledger, the snapshots, their cache and the catalogue bench underneath."""

    homes: DatabaseAccess
    catalogue: CatalogueBench
    cache: EntitlementCache
    ledger: SubscriptionLedger
    snapshots: EntitlementSnapshots
    clock: Clock = field(default_factory=Clock)

    def without_database(self) -> EntitlementSnapshots:
        """Snapshots over the same cache with no database to read."""
        return EntitlementSnapshots(self.unreachable(), self.cache, self.clock)

    @staticmethod
    def unreachable() -> HomeTransactions:
        """Transactions whose every home is out of reach."""
        return cast("HomeTransactions", HomesUnreachable())

    async def subscribe(
        self,
        owner: tuple[Home, UUID],
        plan: tuple[str, str],
        lasting: timedelta = timedelta(days=30),
        queued: tuple[tuple[UUID, int], ...] = (),
    ) -> int:
        """Record a monthly subscription to the plan `(id, slug)` in a committed transaction."""
        home, user_id = owner
        state = SubscriptionTerms(
            PlanRef(UUID(plan[0]), plan[1]),
            billing_period=BillingPeriod.MONTH,
            started_at=self.clock.now - timedelta(days=1),
            expires_at=self.clock.now + lasting,
            queued=queued,
        )
        scope = TenancyScope(home, user_id)
        async with self.homes.transactions.begin(scope) as session:
            return await self.ledger.record(session, user_id, state)


@pytest_asyncio.fixture
async def entitlements(
    catalogue: CatalogueBench, homes: DatabaseAccess, valkey: Redis
) -> AsyncIterator[EntitlementBench]:
    """The bench over the slot's homes and Valkey."""
    cache = EntitlementCache(valkey)
    outbox = EventOutbox(EventTypes(BILLING.events))
    clock = Clock()
    yield EntitlementBench(
        homes=homes,
        catalogue=catalogue,
        cache=cache,
        ledger=SubscriptionLedger(outbox, cache),
        snapshots=EntitlementSnapshots(homes.transactions, cache, clock),
        clock=clock,
    )
