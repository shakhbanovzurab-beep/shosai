"""A BRIN index of provider_costs by time, for the hourly reconciliation (F6 step 9b).

The reconciliation counts each home's rows of one hour; without an index leading on
`created_at` that is a scan of the month's partition every hour. Rows arrive almost in
time order, so a BRIN index of a few pages answers it; `autosummarize` summarises new
ranges as they fill. The index is created on the partitioned table, so every partition —
those core's upkeep adds included — gets its own.
"""

from alembic import op

from shosai.core.db.migration_scope import EVERY_HOME, MigrationScope, runs_in

revision: str = "0dee1c02fdf7"
down_revision: str | None = "a4c2e8f1d903"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME


@runs_in(applies_to)
def upgrade(_scope: MigrationScope) -> None:
    """Index the cost rows by time."""
    op.create_index(
        "ix_provider_costs_created_brin",
        "provider_costs",
        ["created_at"],
        postgresql_using="brin",
        postgresql_with={"autosummarize": "on"},
    )


@runs_in(applies_to)
def downgrade(_scope: MigrationScope) -> None:
    """Drop the index."""
    op.drop_index("ix_provider_costs_created_brin", table_name="provider_costs")
