"""Sales inquiries: a person's request about a custom-priced plan, in their home (step 6).

The work email, company and message are the person's own data and stay in their home;
the owner is told through alerting with ids and the team size only (ADR 0052).
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

revision: str = "d4a8b1f3e602"
down_revision: str | None = "c93f5a2e7d18"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME

TEAM_SIZES = "'1-10', '11-50', '51-200', '201-1000', '1000+'"


def check(sql: str, name: str) -> sa.CheckConstraint:
    """A check constraint of the table, named by the project's convention."""
    return sa.CheckConstraint(sql, name=op.f(f"ck_sales_inquiries_{name}"))


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Create the inquiries, personal by row-level security."""
    op.create_table(
        "sales_inquiries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("work_email", sa.Text(), nullable=False),
        sa.Column("company", sa.Text(), nullable=False),
        sa.Column("team_size", sa.Text(), nullable=False),
        sa.Column("message", sa.Text(), server_default="", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        check("length(work_email) BETWEEN 3 AND 254", "email_length"),
        check("length(company) BETWEEN 1 AND 120", "company_length"),
        check(f"team_size IN ({TEAM_SIZES})", "team_size_known"),
        check("length(message) <= 2000", "message_length"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sales_inquiries")),
    )
    op.create_index("ix_sales_inquiries_user", "sales_inquiries", ["user_id"])
    enable_user_isolation("sales_inquiries")
    grant_to_application(scope, "sales_inquiries", ("SELECT", "INSERT", "DELETE"))


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop the inquiries."""
    revoke_from_application(scope, "sales_inquiries")
    disable_user_isolation("sales_inquiries")
    op.drop_table("sales_inquiries")
