"""The profile's time zone follows the browser until the person fixes one (identity step 17).

`users.timezone_auto` is true for every account, the existing ones included: the cabinet
then saves the browser's zone at the person's next entry. A registration keeps the zone
of the browser it came from in `pending_registrations.timezone` until its code is
confirmed (ADR 0058). Every home.
"""

import sqlalchemy as sa
from alembic import op

from shosai.core.db.migration_scope import EVERY_HOME, MigrationScope, runs_in

revision: str = "bdeb91c94598"
down_revision: str | None = "e0ff4122f875"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME

PENDING_ZONE_CHECK = "ck_pending_registrations_timezone_length"


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Add the zone's mode to the accounts and the browser's zone to the registrations."""
    del scope
    op.add_column(
        "users",
        sa.Column("timezone_auto", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    op.add_column("pending_registrations", sa.Column("timezone", sa.Text(), nullable=True))
    op.create_check_constraint(
        op.f(PENDING_ZONE_CHECK),
        "pending_registrations",
        "timezone IS NULL OR length(timezone) BETWEEN 1 AND 64",
    )


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop both columns; a fixed zone stays as the profile's zone."""
    del scope
    op.drop_constraint(op.f(PENDING_ZONE_CHECK), "pending_registrations", type_="check")
    op.drop_column("pending_registrations", "timezone")
    op.drop_column("users", "timezone_auto")
