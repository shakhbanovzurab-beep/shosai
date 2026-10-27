"""A run's final taint in each home (decisions step 7; DL-D5, Leo §7.4).

A run keeps how far untrusted text reached it when it ended: none, external, or suspicious
when `content.injection` found text giving Leo instructions — what memory's admission reads.
Every earlier run reads as none: the column is added with its default, no row is rewritten.
"""

import sqlalchemy as sa
from alembic import op

from shosai.core.db.migration_scope import EVERY_HOME, MigrationScope, runs_in

revision: str = "a1a96ace53e1"
down_revision: str | None = "f27ce6305d53"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Add the taint and its levels."""
    del scope
    op.add_column(
        "agent_runs",
        sa.Column("taint", sa.SmallInteger(), server_default="0", nullable=False),
    )
    op.create_check_constraint(
        op.f("ck_agent_runs_taint_level"), "agent_runs", "taint BETWEEN 0 AND 2"
    )


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop them."""
    del scope
    op.drop_constraint(op.f("ck_agent_runs_taint_level"), "agent_runs", type_="check")
    op.drop_column("agent_runs", "taint")
