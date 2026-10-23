"""A column's colour and collapse in each home (tasks step 4; TK-D12, §3.14).

A column has one of the palette's nine colours or none, and the person collapses it; both
are the person's view of their own board, so a Jira board's column takes them too.
"""

import sqlalchemy as sa
from alembic import op

from shosai.core.db.migration_scope import EVERY_HOME, MigrationScope, runs_in

revision: str = "b7d1f3a9c524"
down_revision: str | None = "a4c6e8b2d397"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME

COLORS = "'gray', 'red', 'orange', 'amber', 'green', 'teal', 'blue', 'violet', 'pink'"


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Add the colour and the collapse."""
    op.add_column("board_columns", sa.Column("color", sa.Text(), nullable=True))
    op.add_column(
        "board_columns",
        sa.Column("collapsed", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.create_check_constraint(
        op.f("ck_board_columns_color_known"),
        "board_columns",
        f"color IS NULL OR color IN ({COLORS})",
    )


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop them."""
    op.drop_constraint(op.f("ck_board_columns_color_known"), "board_columns", type_="check")
    op.drop_column("board_columns", "collapsed")
    op.drop_column("board_columns", "color")
