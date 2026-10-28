"""The grant lifecycle over the connect bench: tokens, revocation, sweeps as workers run them."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

import pytest_asyncio
from prometheus_client import CollectorRegistry
from sqlalchemy import select, update

from shosai.core.config.roles import ProcessRole
from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.connectors.application.disconnect import Disconnector
from shosai.features.connectors.application.grant_tokens import GrantTokens, TokenTools
from shosai.features.connectors.application.lifecycle_sweeps import DueGrants
from shosai.features.connectors.application.revocation import GrantRevoker, RevokeTools
from shosai.features.connectors.domain.catalogue import App
from shosai.features.connectors.infrastructure.metrics import ConnectorsMetrics
from shosai.features.connectors.infrastructure.store.records import GrantRecord, GrantSecretRecord
from tests.features.connectors.connect_bench import ConnectBench
from tests.harness.database_access import ProcessShape, open_database_access, slot_urls
from tests.harness.run_slot import RunSlot

type Person = tuple[Home, UUID]


@dataclass(frozen=True, slots=True)
class LifecycleBench:
    """The connect bench and the lifecycle's parts over it."""

    connect: ConnectBench
    tokens: GrantTokens
    revoker: GrantRevoker
    disconnector: Disconnector
    metrics: CollectorRegistry
    run_slot: RunSlot

    async def connected(self, person: Person, app: App, account: str = "anna") -> UUID:
        """Connect the app through the flow; the grant's id."""
        await self.connect.finish(await self.connect.start(person, app), f"ok:{account}")
        home, user_id = person
        async with self.connect.homes.transactions.begin(TenancyScope(home, user_id)) as s:
            found = await s.scalar(
                select(GrantRecord.id).where(GrantRecord.external_account_id == account)
            )
        assert found is not None
        return found

    async def expire(self, person: Person, grant_id: UUID) -> None:
        """Make the grant's access token one that must be refreshed."""
        home, user_id = person
        async with self.connect.homes.transactions.begin(TenancyScope(home, user_id)) as s:
            await s.execute(
                update(GrantSecretRecord)
                .where(GrantSecretRecord.grant_id == grant_id)
                .values(expires_at=GrantSecretRecord.refreshed_at - timedelta(hours=1))
            )

    @asynccontextmanager
    async def workers(self) -> AsyncIterator[HomeTransactions]:
        """Transactions as the workers open them: sweeps take the sweep role."""
        shape = ProcessShape(role=ProcessRole.WORKERS)
        async with open_database_access(slot_urls(self.run_slot), shape) as workers:
            yield workers.transactions

    def due(self, transactions: HomeTransactions) -> DueGrants:
        """The sweeps over the workers' transactions."""
        return DueGrants(transactions)


@pytest_asyncio.fixture
async def lifecycle(connect_bench: ConnectBench, run_slot: RunSlot) -> LifecycleBench:
    """The lifecycle with the double providers and fresh counters."""
    registry, http, outbox = connect_bench.wiring
    counters = CollectorRegistry()
    metrics = ConnectorsMetrics(counters)
    transactions = connect_bench.homes.transactions
    tokens = GrantTokens(
        transactions, TokenTools(registry, http, connect_bench.keys, outbox, metrics)
    )
    revoker = GrantRevoker(transactions, RevokeTools(registry, http, connect_bench.keys, metrics))
    disconnector = Disconnector(transactions, outbox, registry)
    return LifecycleBench(connect_bench, tokens, revoker, disconnector, counters, run_slot)
