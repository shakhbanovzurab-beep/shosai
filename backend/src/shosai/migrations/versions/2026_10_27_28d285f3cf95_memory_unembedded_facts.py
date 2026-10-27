"""The path to facts waiting for a vector (memory step 4).

The embedding pass looks once a minute per home for current and waiting facts without a
vector; a partial index on the person keeps that read to the facts that wait, whatever the
size of the table. A model change is rare and is served by the same read without the index.
"""

import sqlalchemy as sa
from alembic import op

from shosai.core.db.migration_scope import EVERY_HOME, MigrationScope, runs_in

revision: str = "28d285f3cf95"
down_revision: str | None = "e8bc01bd5bb4"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME

WAITING = sa.text("embedding IS NULL AND valid_to IS NULL AND status IN ('active', 'candidate')")


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Index the facts waiting for a vector by person."""
    op.create_index(
        "ix_memory_facts_unembedded", "memory_facts", ["user_id", "id"], postgresql_where=WAITING
    )


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop the index."""
    op.drop_index("ix_memory_facts_unembedded", table_name="memory_facts")
