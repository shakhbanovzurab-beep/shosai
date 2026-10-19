"""A rewrite's layout and the run whose findings a write-up lists (every home, meetings step 6).

`meeting_processing_runs.layout` keeps the template a person chose for a rewrite and its
sections as they were at the request, since a person's template is readable only in their
own scope and the stage runs in the meeting's. `meeting_notes.findings_run_id` names the
run whose findings the write-up lists: a rewrite keeps them, and their ids, as they were.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from shosai.core.db.migration_scope import EVERY_HOME, MigrationScope, runs_in

revision: str = "d9f3b7a1c246"
down_revision: str | None = "c7d1e5f3a824"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME

LAYOUT_OBJECT = "ck_meeting_processing_runs_layout_object"


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Add the rewrite's layout and the write-up's findings run."""
    del scope
    op.add_column(
        "meeting_processing_runs",
        sa.Column("layout", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_check_constraint(
        op.f(LAYOUT_OBJECT),
        "meeting_processing_runs",
        "layout IS NULL OR jsonb_typeof(layout) = 'object'",
    )
    op.add_column("meeting_notes", sa.Column("findings_run_id", sa.Uuid(), nullable=True))


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop both columns; a write-up then lists no findings until it is written again."""
    del scope
    op.drop_column("meeting_notes", "findings_run_id")
    op.drop_constraint(op.f(LAYOUT_OBJECT), "meeting_processing_runs", type_="check")
    op.drop_column("meeting_processing_runs", "layout")
