"""The traces of what a person forgot or turned down (memory, ADR 0071 MM-D9).

A forgotten, turned-down or replaced fact is deleted a day after it ended, once it can no
longer be taken back. What the person forgot or turned down leaves a trace without its text —
the vector, its model and the moment — so admission does not ask the same again for 90 days.
The trace is personal by row-level security; the sweep role reads it to find the people the
daily upkeep tends. Existing ended facts are deleted, and traced, by the hourly pass.
"""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import HALFVEC

from shosai.core.db.migration_scope import (
    EVERY_HOME,
    MigrationScope,
    disable_user_isolation,
    enable_user_isolation,
    grant_to_application,
    grant_to_sweeper,
    revoke_from_application,
    revoke_from_sweeper,
    runs_in,
)

revision: str = "f7b43274772a"
down_revision: str | None = "60cb2ba1c6aa"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME

TABLE = "memory_refusals"


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Create the traces, personal and read by the sweep role."""
    op.create_table(
        TABLE,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("embedding", HALFVEC(1024), nullable=False),
        sa.Column("embedding_model", sa.Text(), nullable=False),
        sa.Column("refused_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_memory_refusals")),
    )
    # Как у фактов: вектор в самой строке, скан следов человека не читает TOAST.
    op.execute("ALTER TABLE memory_refusals ALTER COLUMN embedding SET STORAGE PLAIN")
    op.create_index("ix_memory_refusals_person", TABLE, ["user_id", "refused_at"])
    enable_user_isolation(TABLE)
    grant_to_application(scope, TABLE)
    grant_to_sweeper(TABLE, ("SELECT",))


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop the traces."""
    revoke_from_sweeper(TABLE)
    revoke_from_application(scope, TABLE)
    disable_user_isolation(TABLE)
    op.drop_table(TABLE)
