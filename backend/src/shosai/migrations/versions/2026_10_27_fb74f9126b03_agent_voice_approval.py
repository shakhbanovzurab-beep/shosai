"""Actions approved by voice in each home (LEO-voice step 8, Leo §8.4, Q-6).

A reversible or compensable card read back in a voice conversation may be approved there: its
`approved_via` takes `voice` beside the screen's `web` and the inbox. Rolling back keeps the
approvals: a voice one becomes `web`, the channel closest to it, before the narrower check
returns.
"""

from alembic import op

from shosai.core.db.migration_scope import EVERY_HOME, MigrationScope, runs_in

revision: str = "fb74f9126b03"
down_revision: str | None = "d237c5ac833f"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME

CHECK = "ck_agent_actions_via_known"


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Allow the voice channel of approval."""
    del scope
    op.drop_constraint(op.f(CHECK), "agent_actions", type_="check")
    op.create_check_constraint(
        op.f(CHECK),
        "agent_actions",
        "approved_via IS NULL OR approved_via IN ('web', 'inbox', 'voice')",
    )


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Voice approvals become web ones; the check returns to two channels."""
    del scope
    op.drop_constraint(op.f(CHECK), "agent_actions", type_="check")
    op.execute("UPDATE agent_actions SET approved_via = 'web' WHERE approved_via = 'voice'")
    op.create_check_constraint(
        op.f(CHECK), "agent_actions", "approved_via IS NULL OR approved_via IN ('web', 'inbox')"
    )
