"""The sweep role reads uploads, to find those past their 24 hours (files step 3).

The sweep lists due uploads across people and closes each in its owner's transaction,
so it needs to read and nothing more.
"""

from shosai.core.db.migration_scope import (
    EVERY_HOME,
    MigrationScope,
    grant_to_sweeper,
    revoke_from_sweeper,
    runs_in,
)

revision: str = "f3a9c1e5b207"
down_revision: str | None = "e7b2c5d9a314"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Let the sweep role read uploads."""
    del scope
    grant_to_sweeper("uploads", ("SELECT",))


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Take the sweep role's reading of uploads back."""
    del scope
    revoke_from_sweeper("uploads")
