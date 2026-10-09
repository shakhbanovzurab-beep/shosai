"""The application's database access over the run's slot, as a process builds it.

The engines reach each home through its PgBouncer under the application role, the same
path production takes; the gate has verified both homes. A test that writes application
data takes the function fixture `homes`, which empties the tables after it.
"""

import time
from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass

import pytest_asyncio
from opentelemetry.sdk.trace import TracerProvider
from prometheus_client import CollectorRegistry
from pydantic import SecretStr

from shosai.core.config.roles import ProcessRole
from shosai.core.db.engines import DatabaseProfile, HomeDatabases
from shosai.core.db.home_checks import HomeGate
from shosai.core.db.metrics import DatabaseMetrics
from shosai.core.db.migrations import MigrationHistory
from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from tests.harness.migrations import clear_homes
from tests.harness.run_slot import RunSlot


@dataclass(frozen=True, slots=True)
class DatabaseAccess:
    """Engines, gate and transactions of an `api` process over the slot."""

    databases: HomeDatabases
    gate: HomeGate
    transactions: HomeTransactions
    metrics: DatabaseMetrics
    registry: CollectorRegistry


def slot_urls(run_slot: RunSlot) -> dict[Home, SecretStr]:
    """The slot's application-role address in each home, through its PgBouncer."""
    return {home: run_slot.claimed.targets(home).application.url() for home in Home}


@dataclass(frozen=True, slots=True)
class ProcessShape:
    """What differs between the processes a test builds: role, pool, tracing, history, time."""

    role: ProcessRole = ProcessRole.API
    profile: DatabaseProfile | None = None
    tracer_provider: TracerProvider | None = None
    history: MigrationHistory | None = None
    clock: Callable[[], float] = time.monotonic


@asynccontextmanager
async def open_database_access(
    urls: Mapping[Home, SecretStr], shape: ProcessShape | None = None
) -> AsyncIterator[DatabaseAccess]:
    """Database access of a process over the addresses, gate not yet run; disposed after."""
    process = shape or ProcessShape()
    registry = CollectorRegistry()
    metrics = DatabaseMetrics(registry)
    databases = HomeDatabases.create(
        urls, process.role, profile=process.profile, tracer_provider=process.tracer_provider
    )
    history = process.history or MigrationHistory.load()
    gate = HomeGate(databases, history, metrics, process.clock)
    try:
        yield DatabaseAccess(
            databases=databases,
            gate=gate,
            transactions=HomeTransactions(databases, gate, metrics),
            metrics=metrics,
            registry=registry,
        )
    finally:
        await databases.dispose()


@pytest_asyncio.fixture(scope="session")
async def database_access(run_slot: RunSlot) -> AsyncIterator[DatabaseAccess]:
    """One verified database access for the whole run; disposed before the slot downgrades."""
    async with open_database_access(slot_urls(run_slot)) as access:
        await access.gate.verify_at_start()
        yield access


@pytest_asyncio.fixture
async def homes(
    run_slot: RunSlot, database_access: DatabaseAccess
) -> AsyncIterator[DatabaseAccess]:
    """The run's database access for a test that writes data; the tables are emptied after it."""
    try:
        yield database_access
    finally:
        await clear_homes(run_slot.claimed)
