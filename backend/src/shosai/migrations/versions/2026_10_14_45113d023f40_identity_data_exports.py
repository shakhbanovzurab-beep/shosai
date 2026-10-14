"""Export jobs, in every home (identity step 7b)."""

import sqlalchemy as sa
from alembic import op

from shosai.core.db.migration_scope import (
    EVERY_HOME,
    MigrationScope,
    grant_to_application,
    revoke_from_application,
    runs_in,
)

revision: str = "45113d023f40"
down_revision: str | None = "53a75abe8fcb"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME

OPEN = "state IN ('queued', 'running')"


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Create the jobs; a purged archive takes its row with it."""
    op.create_table(
        "data_export_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ready_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("object_key", sa.Text(), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "state IN ('queued', 'running', 'ready', 'failed')",
            name=op.f("ck_data_export_jobs_state_known"),
        ),
        sa.CheckConstraint(
            "attempts BETWEEN 0 AND 10", name=op.f("ck_data_export_jobs_attempts_bounded")
        ),
        sa.CheckConstraint(
            "(state = 'ready') = (ready_at IS NOT NULL AND expires_at IS NOT NULL "
            "AND object_key IS NOT NULL AND size_bytes IS NOT NULL)",
            name=op.f("ck_data_export_jobs_ready_archive"),
        ),
        sa.CheckConstraint(
            "(state = 'failed') = (error_code IS NOT NULL)",
            name=op.f("ck_data_export_jobs_failed_with_code"),
        ),
        sa.CheckConstraint(
            "size_bytes IS NULL OR size_bytes >= 0",
            name=op.f("ck_data_export_jobs_size_not_negative"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_data_export_jobs_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_data_export_jobs")),
    )
    op.create_index(
        "uq_data_export_jobs_open",
        "data_export_jobs",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text(OPEN),
    )
    op.create_index(
        "ix_data_export_jobs_due",
        "data_export_jobs",
        ["run_at", "id"],
        postgresql_where=sa.text(OPEN),
    )
    op.create_index("ix_data_export_jobs_user", "data_export_jobs", ["user_id", "requested_at"])
    op.create_index(
        "ix_data_export_jobs_expires",
        "data_export_jobs",
        ["expires_at"],
        postgresql_where=sa.text("state = 'ready'"),
    )
    grant_to_application(scope, "data_export_jobs", ("SELECT", "INSERT", "UPDATE", "DELETE"))


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop the jobs."""
    revoke_from_application(scope, "data_export_jobs")
    op.drop_table("data_export_jobs")
