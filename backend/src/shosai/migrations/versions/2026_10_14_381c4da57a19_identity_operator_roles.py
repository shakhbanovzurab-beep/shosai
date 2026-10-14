"""Operator roles, in every home (identity step 8a)."""

import sqlalchemy as sa
from alembic import op

from shosai.core.db.migration_scope import (
    EVERY_HOME,
    MigrationScope,
    grant_to_application,
    revoke_from_application,
    runs_in,
)

revision: str = "381c4da57a19"
down_revision: str | None = "45113d023f40"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Create the roles; an owner changes them, so the application may delete them too."""
    op.create_table(
        "operator_roles",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("granted_by", sa.Uuid(), nullable=True),
        sa.Column(
            "granted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "role IN ('owner', 'support', 'finance', 'platform', 'releases', 'read_only')",
            name=op.f("ck_operator_roles_role_known"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_operator_roles_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "role", name="pk_operator_roles"),
    )
    op.create_index("ix_operator_roles_role", "operator_roles", ["role"])
    grant_to_application(scope, "operator_roles", ("SELECT", "INSERT", "DELETE"))


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop the roles."""
    revoke_from_application(scope, "operator_roles")
    op.drop_table("operator_roles")
