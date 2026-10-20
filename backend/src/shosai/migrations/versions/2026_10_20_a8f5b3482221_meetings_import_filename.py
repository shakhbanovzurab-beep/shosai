"""The name an imported recording came with, on its run (every home, meetings step 9b).

`meeting_processing_runs.source_filename` keeps the file's name as it was sent, at most
512 characters: the native clients show it on the import's job while the meeting's title
can be renamed. Runs made before have none; their jobs answer the meeting's title.
"""

import sqlalchemy as sa
from alembic import op

from shosai.core.db.migration_scope import EVERY_HOME, MigrationScope, runs_in

revision: str = "a8f5b3482221"
down_revision: str | None = "a7c3e9f2b158"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME

LENGTH = "ck_meeting_processing_runs_source_filename_length"


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Add the file's name."""
    del scope
    op.add_column("meeting_processing_runs", sa.Column("source_filename", sa.Text(), nullable=True))
    op.create_check_constraint(
        op.f(LENGTH), "meeting_processing_runs", "length(source_filename) BETWEEN 1 AND 512"
    )


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop it; jobs then answer the meeting's title."""
    del scope
    op.drop_constraint(op.f(LENGTH), "meeting_processing_runs", type_="check")
    op.drop_column("meeting_processing_runs", "source_filename")
