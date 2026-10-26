"""The sweep role reads the ratings of Leo's answers, to count them for the operator (agent step
16a; ADR 0068 AG-D5, AG-D13).

Leo in the admin panel answers how people rated Leo's answers with counts over both homes; the
agent workers count them in a read-only sweep, which reads every person's ratings to count and
nothing else. A downgrade closes the ratings to the sweep role.
"""

from shosai.core.db.migration_scope import (
    EVERY_HOME,
    MigrationScope,
    grant_to_sweeper,
    revoke_from_sweeper,
    runs_in,
)

revision: str = "5979d6f23013"
down_revision: str | None = "d240dbd34233"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME

FEEDBACK = "agent_feedback"


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Let the sweep role read the ratings."""
    del scope
    grant_to_sweeper(FEEDBACK, ("SELECT",))


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Close the ratings to the sweep role."""
    del scope
    revoke_from_sweeper(FEEDBACK)
