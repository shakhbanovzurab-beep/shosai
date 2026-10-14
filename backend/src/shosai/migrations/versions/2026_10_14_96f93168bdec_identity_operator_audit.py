"""The operators' audit log, in the EU home only (identity step 8a).

Ids and codes only, monthly partitions kept 12 months (nfr-17); core's upkeep creates them
two months ahead and drops the expired ones. The application may insert and read: an
audit row is never changed or deleted by the application.
"""

import sqlalchemy as sa
from alembic import op

from shosai.core.db.migration_scope import (
    MigrationScope,
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
from shosai.core.kernel.homes import Home

revision: str = "96f93168bdec"
down_revision: str | None = "381c4da57a19"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = (Home.EU,)

AUDIT = MonthlyPartitions("operator_audit_events", ahead_months=2, keep_months=12)


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Create the partitioned audit log, insert and read only for the application."""
    op.create_table(
        "operator_audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("operator_id", sa.Uuid(), nullable=True),
        sa.Column("target_user_id", sa.Uuid(), nullable=False),
        sa.Column("target_home", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("reason_code", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "action IN ('operator_roles_changed', 'account_blocked', 'account_unblocked', "
            "'account_banned')",
            name=op.f("ck_operator_audit_events_action_known"),
        ),
        sa.CheckConstraint(
            "target_home IN ('ru', 'eu')", name=op.f("ck_operator_audit_events_target_home_known")
        ),
        sa.CheckConstraint(
            "reason_code IS NULL OR reason_code ~ '^[a-z0-9_.:-]{1,64}$'",
            name=op.f("ck_operator_audit_events_reason_code_form"),
        ),
        sa.PrimaryKeyConstraint("id", "created_at", name="pk_operator_audit_events"),
        postgresql_partition_by=monthly_partition_range("created_at"),
    )
    op.create_index(
        "ix_operator_audit_events_target",
        "operator_audit_events",
        ["target_user_id", "created_at"],
    )
    op.create_index(
        "ix_operator_audit_events_operator", "operator_audit_events", ["operator_id", "created_at"]
    )
    grant_to_application(scope, "operator_audit_events", ("SELECT", "INSERT"))
    register_monthly_partitions(AUDIT)


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop the audit log with its partitions."""
    unregister_monthly_partitions(AUDIT.table)
    revoke_from_application(scope, "operator_audit_events")
    op.drop_table("operator_audit_events")
