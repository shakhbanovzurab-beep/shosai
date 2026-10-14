"""The account transfer journal, in every home (identity step 9).

A transfer purges the account row from the home it leaves, so the application may now
delete from `users` too; erasure still only anonymises the row.
"""

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

revision: str = "a2d9b4709a2e"
down_revision: str | None = "62331a1a0c29"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME

OPEN = "step IN ('freeze', 'copy', 'verify', 'switch', 'bump', 'purge', 'cancelling')"
STEPS = "'freeze', 'copy', 'verify', 'switch', 'bump', 'purge', 'cancelling', 'done', 'cancelled'"


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Create the journal; let the application purge an account row it moved away."""
    op.create_table(
        "home_transfers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("from_home", sa.Text(), nullable=False),
        sa.Column("to_home", sa.Text(), nullable=False),
        sa.Column("step", sa.Text(), nullable=False),
        sa.Column("prior_state", sa.Text(), nullable=True),
        sa.Column("requested_by", sa.Uuid(), nullable=True),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "copied_owners", postgresql.ARRAY(sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column("manifest", postgresql.JSONB(), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(f"step IN ({STEPS})", name=op.f("ck_home_transfers_step_known")),
        sa.CheckConstraint(
            "from_home IN ('ru', 'eu') AND to_home IN ('ru', 'eu') AND from_home <> to_home",
            name=op.f("ck_home_transfers_homes_differ"),
        ),
        sa.CheckConstraint("attempts >= 0", name=op.f("ck_home_transfers_attempts_not_negative")),
        sa.CheckConstraint(
            "(step IN ('done', 'cancelled')) = (finished_at IS NOT NULL)",
            name=op.f("ck_home_transfers_finished"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_home_transfers")),
    )
    op.create_index(
        "uq_home_transfers_open",
        "home_transfers",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text(OPEN),
    )
    op.create_index(
        "ix_home_transfers_due", "home_transfers", ["run_at", "id"], postgresql_where=sa.text(OPEN)
    )
    op.create_index("ix_home_transfers_finished", "home_transfers", ["finished_at"])
    grant_to_application(scope, "home_transfers", ("SELECT", "INSERT", "UPDATE", "DELETE"))
    grant_to_application(scope, "users", ("DELETE",))


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop the journal; the application no longer deletes account rows."""
    revoke_from_application(scope, "users")
    grant_to_application(scope, "users", ("SELECT", "INSERT", "UPDATE"))
    revoke_from_application(scope, "home_transfers")
    op.drop_table("home_transfers")
