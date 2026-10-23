"""Agent's threads before their first question, and a workspace's threads found at once (agent
step 4).

A thread is made when its first question is sent and is titled by it, so its title is null
until then; the title's length check already admits null. A deleted workspace's threads are
erased at once, person by person: the sweep finds the people by the workspace through a
partial index of workspace threads. A downgrade titles the untitled threads with an ellipsis.
"""

import sqlalchemy as sa
from alembic import op

from shosai.core.db.migration_scope import EVERY_HOME, MigrationScope, runs_in

revision: str = "9a43ed077e60"
down_revision: str | None = "a6c8e2f4b917"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME

INDEX = "ix_agent_threads_workspace"


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Allow an untitled thread; index workspace threads by workspace and person."""
    del scope
    op.alter_column("agent_threads", "title", existing_type=sa.Text(), nullable=True)
    op.create_index(
        INDEX,
        "agent_threads",
        ["org_id", "user_id"],
        postgresql_where=sa.text("org_id IS NOT NULL"),
    )


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop the index; untitled threads take an ellipsis and the title is required again."""
    del scope
    op.drop_index(INDEX, table_name="agent_threads")
    op.execute("UPDATE agent_threads SET title = '…' WHERE title IS NULL")
    op.alter_column("agent_threads", "title", existing_type=sa.Text(), nullable=False)
