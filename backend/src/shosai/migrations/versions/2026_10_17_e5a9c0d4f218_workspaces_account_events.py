"""The time of the last account event a membership applied (workspaces step 4).

identity's deletion window hides an account's memberships and a cancellation shows them
again (ADR 0053 point 4). The two events may be delivered out of order; a membership
applies an event only if it is newer than the last one it applied.
"""

import sqlalchemy as sa
from alembic import op

from shosai.core.db.migration_scope import EVERY_HOME, MigrationScope, runs_in

revision: str = "e5a9c0d4f218"
down_revision: str | None = "d82f3b6c1e47"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Add the time of the last applied account event."""
    op.add_column(
        "memberships", sa.Column("account_event_at", sa.DateTime(timezone=True), nullable=True)
    )


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop the time of the last applied account event."""
    op.drop_column("memberships", "account_event_at")
