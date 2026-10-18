"""A person's files hidden while identity's deletion window runs (files step 7, ADR 0045 point 6).

Every personal file row of the account says the account is hidden, so the one read path
of files leaves it out for every viewer; the usage row keeps the time of the last account
event applied, so events delivered out of order end where the latest one says.
"""

import sqlalchemy as sa
from alembic import op

from shosai.core.db.migration_scope import EVERY_HOME, MigrationScope, runs_in

revision: str = "c4f9a1e7d250"
down_revision: str | None = "b6e2d8f4a173"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Add the account's hiding to files and usage, and the time of its last event."""
    del scope
    op.add_column(
        "storage_files",
        sa.Column("account_hidden", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "storage_usage",
        sa.Column("account_hidden", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "storage_usage", sa.Column("account_event_at", sa.DateTime(timezone=True), nullable=True)
    )


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop the account's hiding and the time of its last event."""
    del scope
    op.drop_column("storage_usage", "account_event_at")
    op.drop_column("storage_usage", "account_hidden")
    op.drop_column("storage_files", "account_hidden")
