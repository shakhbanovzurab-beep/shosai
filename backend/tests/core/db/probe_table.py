"""A probe table with company isolation in both homes, for tests that write rows.

A pytest plugin of the root `conftest.py`: the database tests and the task tests share it.
"""

from collections.abc import AsyncIterator

import pytest_asyncio
import sqlalchemy as sa
from alembic import op

from shosai.core.db.migration_scope import (
    MigrationScope,
    disable_company_isolation,
    enable_company_isolation,
    grant_to_application,
)
from tests.core.db.operations import run_step_everywhere
from tests.harness.run_slot import RunSlot

PROBE_TABLE = "probe_records"
probe_records = sa.table(
    PROBE_TABLE,
    sa.column("id", sa.Uuid()),
    sa.column("org_id", sa.Uuid()),
    sa.column("note", sa.Text()),
)


def create_probe_table(scope: MigrationScope) -> None:
    """A company-scoped table as a slice would declare it, open to the application role."""
    op.create_table(
        PROBE_TABLE,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("org_id", sa.Uuid(), nullable=True),
        sa.Column("note", sa.Text(), nullable=False),
    )
    grant_to_application(scope, PROBE_TABLE)
    enable_company_isolation(PROBE_TABLE)


def drop_probe_table(_scope: MigrationScope) -> None:
    """Undo `create_probe_table`."""
    disable_company_isolation(PROBE_TABLE)
    op.drop_table(PROBE_TABLE)


@pytest_asyncio.fixture
async def probe_table(run_slot: RunSlot) -> AsyncIterator[sa.TableClause]:
    """`probe_records` in both homes for one test; dropped after it."""
    await run_step_everywhere(run_slot, create_probe_table)
    try:
        yield probe_records
    finally:
        await run_step_everywhere(run_slot, drop_probe_table)
