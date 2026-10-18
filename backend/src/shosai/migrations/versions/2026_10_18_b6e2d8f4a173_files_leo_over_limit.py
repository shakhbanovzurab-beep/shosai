"""Leo over the knowledge limit for 90 days (files step 6b, FL-D10).

A person's usage row carries since when Leo uses more than `knowledge_base_mb` and how
many of the three reminders went; a file Leo stopped reading through its folder on day 90
is held out of the folder's use until the person switches it on. The daily pass reads
the folders' switches through the sweep role.
"""

import sqlalchemy as sa
from alembic import op

from shosai.core.db.migration_scope import (
    EVERY_HOME,
    MigrationScope,
    grant_to_sweeper,
    revoke_from_sweeper,
    runs_in,
)

revision: str = "b6e2d8f4a173"
down_revision: str | None = "a7d3e9f1c428"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME

CHECKS = (
    ("leo_reminders_range", "leo_reminders_sent BETWEEN 0 AND 3"),
    ("leo_reminders_while_over", "leo_over_limit_since IS NOT NULL OR leo_reminders_sent = 0"),
)


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Add Leo's mark over the limit, its reminders and the files' hold."""
    del scope
    op.add_column(
        "storage_usage",
        sa.Column("leo_over_limit_since", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "storage_usage",
        sa.Column("leo_reminders_sent", sa.SmallInteger(), server_default="0", nullable=False),
    )
    for name, condition in CHECKS:
        op.create_check_constraint(op.f(f"ck_storage_usage_{name}"), "storage_usage", condition)
    op.add_column(
        "storage_files",
        sa.Column("leo_held", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    grant_to_sweeper("file_folders", ("SELECT",))


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop the hold, the reminders and the mark, and close the folders to the sweep role."""
    del scope
    revoke_from_sweeper("file_folders")
    op.drop_column("storage_files", "leo_held")
    for name, _ in CHECKS:
        op.drop_constraint(op.f(f"ck_storage_usage_{name}"), "storage_usage", type_="check")
    op.drop_column("storage_usage", "leo_reminders_sent")
    op.drop_column("storage_usage", "leo_over_limit_since")
