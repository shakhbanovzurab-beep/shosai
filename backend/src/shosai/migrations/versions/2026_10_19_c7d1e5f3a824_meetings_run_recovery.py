"""The sweep role reads runs, so the recovery finds stages whose tasks are lost (meetings step 5).

The recovery sweep lists unfinished runs across tenants; each stage is sent again in its
meeting's scope, and its claim under the run's lock decides whether it runs.
"""

from shosai.core.db.migration_scope import (
    EVERY_HOME,
    MigrationScope,
    grant_to_sweeper,
    revoke_from_sweeper,
    runs_in,
)

revision: str = "c7d1e5f3a824"
down_revision: str | None = "b4e8f2a6c913"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Let the sweep role read runs."""
    del scope
    grant_to_sweeper("meeting_processing_runs", ("SELECT",))


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Close runs to the sweep role again."""
    del scope
    revoke_from_sweeper("meeting_processing_runs")
