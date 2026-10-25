"""The sweep role reads Leo's action audit for the hourly check of its invariants (agent step
9a2; Leo L-N5).

The check counts, per home, the items the audit shows executed twice under their key and those
executed without an `approved` row, so it reads every person's audit rows; the audit stays
append-only for the application, and the sweep role may only read it. A downgrade closes it
to the sweep role again.
"""

from shosai.core.db.migration_scope import (
    EVERY_HOME,
    MigrationScope,
    grant_to_sweeper,
    revoke_from_sweeper,
    runs_in,
)

revision: str = "92bc6bf92c5e"
down_revision: str | None = "9a43ed077e60"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME

AUDIT = "agent_audit"


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Let the sweep role read the action audit."""
    del scope
    grant_to_sweeper(AUDIT, ("SELECT",))


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Close the action audit to the sweep role."""
    del scope
    revoke_from_sweeper(AUDIT)
