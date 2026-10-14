"""Refresh families and the sign-in log, in every home (identity step 3a).

The sign-in log has monthly partitions kept 12 months (§8.2); core's upkeep creates them
two months ahead and drops the expired ones.
"""

from datetime import datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from shosai.core.db.migration_scope import (
    EVERY_HOME,
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

revision: str = "cdffee633555"
down_revision: str | None = "a4a15f84ccdc"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME

LOGIN_EVENTS = MonthlyPartitions("login_events", ahead_months=2, keep_months=12)


def check(table: str, sql: str, name: str) -> sa.CheckConstraint:
    """A check constraint named by the project's convention."""
    return sa.CheckConstraint(sql, name=op.f(f"ck_{table}_{name}"))


def moment(name: str, *, default_now: bool = False, nullable: bool = False) -> sa.Column[datetime]:
    """A timestamp column with a time zone."""
    default = sa.func.now() if default_now else None
    return sa.Column(name, sa.DateTime(timezone=True), server_default=default, nullable=nullable)


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Create the refresh families and the partitioned sign-in log."""
    create_refresh_sessions(scope)
    create_login_events(scope)


def create_refresh_sessions(scope: MigrationScope) -> None:
    """The families; rows are rotated and revoked, and purged 30 days after they end."""
    op.create_table(
        "refresh_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("client_kind", sa.Text(), nullable=False),
        sa.Column("generation", sa.Integer(), server_default="0", nullable=False),
        sa.Column("current_id_hash", sa.LargeBinary(), nullable=False),
        sa.Column("previous_id_hash", sa.LargeBinary(), nullable=True),
        moment("rotated_at", nullable=True),
        moment("expires_at"),
        moment("revoked_at", nullable=True),
        sa.Column("revoke_reason", sa.Text(), nullable=True),
        sa.Column("device_label", sa.Text(), nullable=True),
        sa.Column("ip", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        moment("created_at", default_now=True),
        moment("last_used_at", default_now=True),
        check("refresh_sessions", "client_kind IN ('web', 'desktop')", "client_kind_known"),
        check("refresh_sessions", "generation >= 0", "generation_not_negative"),
        check("refresh_sessions", "length(current_id_hash) = 32", "current_id_hash_length"),
        check(
            "refresh_sessions",
            "user_agent IS NULL OR length(user_agent) <= 512",
            "user_agent_length",
        ),
        check(
            "refresh_sessions",
            "device_label IS NULL OR length(device_label) <= 128",
            "device_label_length",
        ),
        check(
            "refresh_sessions",
            "(revoked_at IS NULL) = (revoke_reason IS NULL)",
            "revoked_with_reason",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_refresh_sessions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refresh_sessions")),
    )
    op.create_index(
        "ix_refresh_sessions_user",
        "refresh_sessions",
        ["user_id"],
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.create_index("ix_refresh_sessions_expires", "refresh_sessions", ["expires_at"])
    grant_to_application(scope, "refresh_sessions", ("SELECT", "INSERT", "UPDATE", "DELETE"))


def create_login_events(scope: MigrationScope) -> None:
    """The sign-in log; appended only, dropped by partition after 12 months."""
    op.create_table(
        "login_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        moment("created_at", default_now=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("client_kind", sa.Text(), nullable=False),
        sa.Column("ip", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        check(
            "login_events", "outcome IN ('success', 'wrong_password', 'blocked')", "outcome_known"
        ),
        check("login_events", "client_kind IN ('web', 'desktop')", "client_kind_known"),
        check(
            "login_events", "user_agent IS NULL OR length(user_agent) <= 512", "user_agent_length"
        ),
        sa.PrimaryKeyConstraint("id", "created_at", name=op.f("pk_login_events")),
        postgresql_partition_by=monthly_partition_range("created_at"),
    )
    op.create_index("ix_login_events_user", "login_events", ["user_id", "created_at"])
    # Стирание аккаунта удаляет его строки журнала входов (реестр, шаг 7), отсюда DELETE.
    grant_to_application(scope, "login_events", ("SELECT", "INSERT", "DELETE"))
    register_monthly_partitions(LOGIN_EVENTS)


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop the sign-in log with its partitions and the refresh families."""
    unregister_monthly_partitions(LOGIN_EVENTS.table)
    revoke_from_application(scope, "login_events")
    op.drop_table("login_events")
    revoke_from_application(scope, "refresh_sessions")
    op.drop_table("refresh_sessions")
