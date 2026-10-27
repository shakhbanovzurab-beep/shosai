"""Voice runs in each home (LEO-voice step 4, ADR 0070 LV-D5).

An exchange of Leo's voice mode is recorded as a run of channel `voice` beside the cabinet's
`web` and the operator's `admin`. Rolling back keeps the runs: a voice run becomes `web`, the
channel closest to it, before the narrower check returns.
"""

from alembic import op

from shosai.core.db.migration_scope import EVERY_HOME, MigrationScope, runs_in

revision: str = "08a5069d5388"
down_revision: str | None = "c1d09d162c37"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME

CHECK = "ck_agent_runs_channel_known"


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Allow the voice channel."""
    del scope
    op.drop_constraint(op.f(CHECK), "agent_runs", type_="check")
    op.create_check_constraint(op.f(CHECK), "agent_runs", "channel IN ('web', 'admin', 'voice')")


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Voice runs become web runs; the check returns to two channels."""
    del scope
    op.drop_constraint(op.f(CHECK), "agent_runs", type_="check")
    op.execute("UPDATE agent_runs SET channel = 'web' WHERE channel = 'voice'")
    op.create_check_constraint(op.f(CHECK), "agent_runs", "channel IN ('web', 'admin')")
