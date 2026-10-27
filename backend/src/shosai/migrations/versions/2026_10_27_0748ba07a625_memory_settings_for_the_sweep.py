"""The sweep role reads memory's switch (memory step 8).

The hourly check of memory's invariant counts, per home, the facts written after their person
switched memory off; it joins the facts with the switch through the sweep role, which already
reads the facts and the summaries. The table keeps its personal row-level security and the sweep
policy every personal table has; only the grant was missing.
"""

from shosai.core.db.migration_scope import (
    EVERY_HOME,
    MigrationScope,
    grant_to_sweeper,
    revoke_from_sweeper,
    runs_in,
)

revision: str = "0748ba07a625"
down_revision: str | None = "28d285f3cf95"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Let the sweep role read the switch."""
    grant_to_sweeper("memory_settings", ("SELECT",))


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Close the switch to the sweep role again."""
    revoke_from_sweeper("memory_settings")
