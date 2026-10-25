"""A run keeps its answer's language, and the sweep role reads Leo's evaluation cases (agent
step 11a; ADR 0068 AG-D13).

An evaluation case keeps the language Leo answered in, so the live suites check the languages
the cases came in; the run records it when it starts, and runs before that have none. The daily
purge lists the people whose cases passed their year, so the sweep role may read the cases;
each person's go in their own transaction. A downgrade closes the cases to the sweep role and
drops the run's language.
"""

import sqlalchemy as sa
from alembic import op

from shosai.core.db.migration_scope import (
    EVERY_HOME,
    MigrationScope,
    grant_to_sweeper,
    revoke_from_sweeper,
    runs_in,
)

revision: str = "3f85ef4b625e"
down_revision: str | None = "92bc6bf92c5e"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME

RUNS = "agent_runs"
CASES = "agent_eval_cases"
LANGUAGE_FORM = "language IS NULL OR language ~ '^[a-z]{2,3}(-[A-Za-z]{2,4})?$'"


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Add the run's language and let the sweep role read the cases."""
    del scope
    op.add_column(RUNS, sa.Column("language", sa.Text(), nullable=True))
    op.create_check_constraint("language_form", RUNS, LANGUAGE_FORM)
    grant_to_sweeper(CASES, ("SELECT",))


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Close the cases to the sweep role and drop the run's language."""
    del scope
    revoke_from_sweeper(CASES)
    op.drop_constraint("language_form", RUNS, type_="check")
    op.drop_column(RUNS, "language")
