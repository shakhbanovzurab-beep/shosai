"""A plan's ceiling of people in one video call (meetings A4, MR-D2).

`tariffs.room_participants` is null for every plan already in the catalogue: a call then takes
the platform's ceiling (50, 4 on staging), the same as before the column. A set value is 2 to
1 000; meetings caps it by the platform's ceiling.
"""

import sqlalchemy as sa
from alembic import op

from shosai.core.db.migration_scope import MigrationScope, runs_in
from shosai.core.kernel.homes import Home

revision: str = "ba9f302663d7"
down_revision: str | None = "3b6722d0ad2b"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = (Home.EU,)

CHECK: str = "ck_tariffs_room_participants_range"


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Add the column and its range."""
    op.add_column("tariffs", sa.Column("room_participants", sa.Integer(), nullable=True))
    op.create_check_constraint(
        op.f(CHECK), "tariffs", "room_participants IS NULL OR room_participants BETWEEN 2 AND 1000"
    )


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop the range and the column."""
    op.drop_constraint(op.f(CHECK), "tariffs", type_="check")
    op.drop_column("tariffs", "room_participants")
