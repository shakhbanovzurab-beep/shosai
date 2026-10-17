"""Minutes: usage tombstones by month and the Free plan's device claims, in each home (step 4).

`usage_events` holds a tombstone per deleted meeting in the month the meeting happened,
so deleting it never gives its minutes back that month (ADR 0007 as amended). Monthly
partitions keep the current and the previous month; the previous month's partition is
created here too, because a meeting of last month may still be deleted. A tombstone is
written once per meeting. `free_plan_devices` claims a desktop device for one Free
account by the SHA-256 of its id (or, for the shipped clients, its machine name); the
unique hash refuses a second account whatever row-level security shows (BL-D3).
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

revision: str = "b7e1d4a90c26"
down_revision: str | None = "a4c2e8f61b93"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME

USAGE = MonthlyPartitions("usage_events", ahead_months=2, keep_months=1)
TABLES = ("usage_events", "free_plan_devices")
PREVIOUS_MONTH = """
DO $$
DECLARE
    month_start timestamptz := date_trunc('month', now()) - interval '1 month';
    child text := format('usage_events_p%s', to_char(month_start, 'YYYYMM'));
BEGIN
    IF to_regclass(child) IS NULL THEN
        EXECUTE format(
            'CREATE TABLE %I (LIKE usage_events INCLUDING DEFAULTS INCLUDING CONSTRAINTS)', child
        );
        EXECUTE format(
            'ALTER TABLE usage_events ATTACH PARTITION %I FOR VALUES FROM (%L) TO (%L)',
            child, month_start, month_start + interval '1 month'
        );
    END IF;
END
$$
"""


def check(table: str, sql: str, name: str) -> sa.CheckConstraint:
    """A check constraint named by the project's convention."""
    return sa.CheckConstraint(sql, name=op.f(f"ck_{table}_{name}"))


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Create the tombstones by month and the device claims, personal by row-level security."""
    op.create_table(
        "usage_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("meeting_id", sa.Uuid(), nullable=False),
        sa.Column("seconds", sa.Integer(), nullable=False),
        sa.Column(
            "recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        check("usage_events", "seconds BETWEEN 0 AND 604800", "seconds_range"),
        sa.PrimaryKeyConstraint("id", "occurred_at", name=op.f("pk_usage_events")),
        postgresql_partition_by=monthly_partition_range("occurred_at"),
    )
    op.create_index("ix_usage_events_user", "usage_events", ["user_id", "occurred_at"])
    op.create_index(
        "uq_usage_events_meeting", "usage_events", ["meeting_id", "occurred_at"], unique=True
    )
    register_monthly_partitions(USAGE)
    op.execute(PREVIOUS_MONTH)
    op.create_table(
        "free_plan_devices",
        sa.Column("device_hash", sa.LargeBinary(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "claimed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        check("free_plan_devices", "octet_length(device_hash) = 32", "hash_length"),
        sa.PrimaryKeyConstraint("device_hash", name=op.f("pk_free_plan_devices")),
    )
    op.create_index("ix_free_plan_devices_user", "free_plan_devices", ["user_id"])
    for table in TABLES:
        enable_user_isolation(table)
        grant_to_application(scope, table)


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop the device claims and the tombstones with their partitions."""
    for table in reversed(TABLES):
        revoke_from_application(scope, table)
        disable_user_isolation(table)
    op.drop_table("free_plan_devices")
    unregister_monthly_partitions(USAGE.table)
    op.drop_table("usage_events")
