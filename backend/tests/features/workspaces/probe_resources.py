"""Two probe tables shaped like a slice's shareable resources: kinds `meeting` and `file`.

They let workspaces test its policy before meetings and files exist: personal rows are
shared through the real share records, workspace rows carry a level and grants.
"""

from collections.abc import AsyncIterator

import pytest_asyncio
import sqlalchemy as sa
from alembic import op

from shosai.core.access.shareable import ShareableResource
from shosai.core.db.migration_scope import (
    MigrationScope,
    disable_company_isolation,
    enable_company_isolation,
    grant_to_application,
)
from tests.core.db.operations import run_step_everywhere
from tests.harness.run_slot import RunSlot

METADATA = sa.MetaData()
NAMES = {"meeting": "probe_meetings", "file": "probe_files"}
TABLES = {
    kind: sa.Table(
        name,
        METADATA,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid()),
        sa.Column("access", sa.Text()),
    )
    for kind, name in NAMES.items()
}
MEETINGS = ShareableResource("meeting", TABLES["meeting"])
FILES = ShareableResource("file", TABLES["file"])


def create_tables(scope: MigrationScope) -> None:
    for table in TABLES.values():
        op.create_table(
            table.name,
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("org_id", sa.Uuid(), nullable=True),
            sa.Column("access", sa.Text(), nullable=True),
        )
        op.create_index(f"ix_{table.name}_org", table.name, ["org_id"])
        op.create_index(f"ix_{table.name}_user", table.name, ["user_id"])
        grant_to_application(scope, table.name)
        enable_company_isolation(table.name)


def drop_tables(_scope: MigrationScope) -> None:
    for table in TABLES.values():
        disable_company_isolation(table.name)
        op.drop_table(table.name)


@pytest_asyncio.fixture
async def probe_resources(run_slot: RunSlot) -> AsyncIterator[None]:
    """Both probe tables in both homes for one test; dropped after it."""
    await run_step_everywhere(run_slot, create_tables)
    try:
        yield
    finally:
        await run_step_everywhere(run_slot, drop_tables)
