"""Schema changes the database tests make through the migration helpers of production.

A test runs a step the way a revision would: under the migration role, directly, inside
an Alembic operations context, in one transaction per home.
"""

from collections.abc import Callable

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Connection, NullPool, make_url
from sqlalchemy.ext.asyncio import create_async_engine

from tests.harness.run_slot import RunSlot
from whisperer.core.db.engines import DRIVER
from whisperer.core.db.migration_scope import MigrationScope
from whisperer.core.kernel.homes import Home

type SchemaStep = Callable[[MigrationScope], None]


async def run_step(run_slot: RunSlot, home: Home, step: SchemaStep) -> None:
    """Run a revision-like step in one home of the slot and commit it."""
    targets = run_slot.claimed.targets(home)
    engine = create_async_engine(
        make_url(targets.migration.url().get_secret_value()).set(drivername=DRIVER),
        poolclass=NullPool,
        connect_args={"prepare_threshold": None},
    )
    scope = MigrationScope(home=home, application_role=targets.application.user)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(_apply, step, scope)
    finally:
        await engine.dispose()


async def run_step_everywhere(run_slot: RunSlot, step: SchemaStep) -> None:
    """Run the step in every home of the slot."""
    for home in Home:
        await run_step(run_slot, home, step)


def _apply(connection: Connection, step: SchemaStep, scope: MigrationScope) -> None:
    with Operations.context(MigrationContext.configure(connection)):
        step(scope)
