"""The last run of each periodic job, in every home (F6 step 1)."""

import sqlalchemy as sa
from alembic import op

from shosai.core.db.migration_scope import (
    EVERY_HOME,
    MigrationScope,
    grant_to_application,
    revoke_from_application,
    runs_in,
)

revision: str = "7f9095f97350"
down_revision: str | None = "eea93a7e0c11"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Create the job runs and let the application create and claim them."""
    op.create_table(
        "schedule_runs",
        sa.Column("job_name", sa.Text(), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "job_name ~ '^[a-z][a-z0-9_]*(\\.[a-z][a-z0-9_]*)+$' AND length(job_name) <= 64",
            name=op.f("ck_schedule_runs_job_name_format"),
        ),
        sa.PrimaryKeyConstraint("job_name", name=op.f("pk_schedule_runs")),
    )
    # Строку задачи код не удаляет: удалённая из кода задача оставляет свою историю.
    grant_to_application(scope, "schedule_runs", ("SELECT", "INSERT", "UPDATE"))


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop the job runs."""
    revoke_from_application(scope, "schedule_runs")
    op.drop_table("schedule_runs")
