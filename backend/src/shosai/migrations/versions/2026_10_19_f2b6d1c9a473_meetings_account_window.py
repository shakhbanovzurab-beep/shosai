"""Whether a person's account waits for its erasure, as meetings knows it (every home, step 8).

Identity's deletion window hides a person's data from everyone until the erasure (ADR 0045
point 6). Meetings keeps the window on the person's setting row, from identity's events:
`account_hidden`, and the time of the last event applied, so events delivered out of order
end where the latest one says. Support neither lists nor restores the meetings of an
account in its window (MT-D8).
"""

import sqlalchemy as sa
from alembic import op

from shosai.core.db.migration_scope import EVERY_HOME, MigrationScope, runs_in

revision: str = "f2b6d1c9a473"
down_revision: str | None = "e5c2a8d4f017"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Add the window's mark and the time of its last event."""
    del scope
    op.add_column(
        "meeting_settings",
        sa.Column("account_hidden", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "meeting_settings",
        sa.Column("account_event_at", sa.DateTime(timezone=True), nullable=True),
    )


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop both."""
    del scope
    op.drop_column("meeting_settings", "account_event_at")
    op.drop_column("meeting_settings", "account_hidden")
