"""The sweep role reads storage usage, for the daily quota check and reconciliation (files step 5).

The check lists the people who hold bytes or are over their limit and acts on each in its
owner's transaction; the reconciliation compares the counters with the files. Both only
read through the sweep role.
"""

from shosai.core.db.migration_scope import (
    EVERY_HOME,
    MigrationScope,
    grant_to_sweeper,
    revoke_from_sweeper,
    runs_in,
)

revision: str = "a7d3e9f1c428"
down_revision: str | None = "f3a9c1e5b207"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Let the sweep role read storage usage."""
    del scope
    grant_to_sweeper("storage_usage", ("SELECT",))


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Take the sweep role's reading of storage usage back."""
    del scope
    revoke_from_sweeper("storage_usage")
