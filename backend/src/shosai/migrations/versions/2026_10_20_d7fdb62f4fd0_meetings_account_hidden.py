"""A person's own meetings hidden while identity's deletion window runs (every home, step 15).

Every personal meeting of an account in its window says so on its row, as files does, so
the one read gate of meetings, `visible_meetings`, leaves it out for every viewer — its
owner, a workspace it is shared in, Leo, other slices' readers — without reading another
person's setting row, which only its person may read. A workspace's meeting is the
workspace's and is never hidden with an account. Meetings of accounts already in their
window are marked from their setting rows.
"""

import sqlalchemy as sa
from alembic import op

from shosai.core.db.migration_scope import EVERY_HOME, MigrationScope, runs_in

revision: str = "d7fdb62f4fd0"
down_revision: str | None = "a8f5b3482221"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Add the mark and set it on the meetings of accounts in their window."""
    del scope
    op.add_column(
        "sessions",
        sa.Column("account_hidden", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.execute(
        "UPDATE sessions SET account_hidden = true FROM meeting_settings"
        " WHERE meeting_settings.user_id = sessions.user_id"
        " AND meeting_settings.account_hidden AND sessions.org_id IS NULL"
    )


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop the mark; the setting rows still hold the window."""
    del scope
    op.drop_column("sessions", "account_hidden")
