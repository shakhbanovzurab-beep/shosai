"""Leo's voice conversations by month in each home (LEO-voice step 5, ADR 0070 LV-D7).

`capture_voice_sessions` holds a row per conversation: its start, the seconds counted so
far — written every minute — and its end with the reason. Billing counts the seconds against
the plan's monthly minutes. Personal by row-level security; monthly partitions keep the
current and the previous month, the previous one created here too, as billing counts it.
"""

import sqlalchemy as sa
from alembic import op

from shosai.core.db.migration_scope import (
    EVERY_HOME,
    MigrationScope,
    disable_user_isolation,
    enable_user_isolation,
    grant_to_application,
    revoke_from_application,
    runs_in,
)
from shosai.core.db.partitions.policy import (
    MonthlyPartitions,
    monthly_partition_range,
    register_monthly_partitions,
    unregister_monthly_partitions,
)

revision: str = "d237c5ac833f"
down_revision: str | None = "08a5069d5388"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME

TABLE = "capture_voice_sessions"
SESSIONS = MonthlyPartitions(TABLE, ahead_months=2, keep_months=1)
END_CODES = (
    "'ended', 'idle', 'time_limit', 'minutes_exhausted', 'server_shutdown', 'voice_unavailable'"
)
PREVIOUS_MONTH = """
DO $$
DECLARE
    parent text := 'capture_voice_sessions';
    month_start timestamptz := date_trunc('month', now()) - interval '1 month';
    child text := format('%s_p%s', parent, to_char(month_start, 'YYYYMM'));
BEGIN
    IF to_regclass(child) IS NULL THEN
        EXECUTE format(
            'CREATE TABLE %I (LIKE %I INCLUDING DEFAULTS INCLUDING CONSTRAINTS)', child, parent
        );
        EXECUTE format(
            'ALTER TABLE %I ATTACH PARTITION %I FOR VALUES FROM (%L) TO (%L)',
            parent, child, month_start, month_start + interval '1 month'
        );
    END IF;
END
$$
"""


def check(sql: str, name: str) -> sa.CheckConstraint:
    """A check constraint named by the project's convention."""
    return sa.CheckConstraint(sql, name=op.f(f"ck_{TABLE}_{name}"))


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Create the conversations by month, personal by row-level security."""
    op.create_table(
        TABLE,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("seconds", sa.Integer(), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_code", sa.Text(), nullable=True),
        check("seconds BETWEEN 0 AND 3600", "seconds_range"),
        check(f"end_code IN ({END_CODES})", "end_known"),
        check("(ended_at IS NULL) = (end_code IS NULL)", "ended_with_code"),
        check("ended_at IS NULL OR ended_at >= started_at", "ends_after_start"),
        sa.PrimaryKeyConstraint("id", "started_at", name=op.f(f"pk_{TABLE}")),
        postgresql_partition_by=monthly_partition_range("started_at"),
    )
    op.create_index("ix_capture_voice_sessions_user", TABLE, ["user_id", "started_at"])
    register_monthly_partitions(SESSIONS)
    op.execute(PREVIOUS_MONTH)
    enable_user_isolation(TABLE)
    grant_to_application(scope, TABLE)


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop the conversations with their partitions."""
    revoke_from_application(scope, TABLE)
    disable_user_isolation(TABLE)
    unregister_monthly_partitions(SESSIONS.table)
    op.drop_table(TABLE)
