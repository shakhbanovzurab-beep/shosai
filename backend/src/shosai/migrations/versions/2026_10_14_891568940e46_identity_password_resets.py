"""Password reset links, in every home (identity step 3b)."""

import sqlalchemy as sa
from alembic import op

from shosai.core.db.migration_scope import (
    EVERY_HOME,
    MigrationScope,
    grant_to_application,
    revoke_from_application,
    runs_in,
)

revision: str = "891568940e46"
down_revision: str | None = "cdffee633555"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Create the reset links; a link is used once, and a new one deletes the older ones."""
    op.create_table(
        "password_reset_tokens",
        sa.Column("token_hash", sa.LargeBinary(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "length(token_hash) = 32", name=op.f("ck_password_reset_tokens_token_hash_length")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_password_reset_tokens_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("token_hash", name=op.f("pk_password_reset_tokens")),
    )
    op.create_index("ix_password_reset_tokens_user", "password_reset_tokens", ["user_id"])
    op.create_index("ix_password_reset_tokens_expires", "password_reset_tokens", ["expires_at"])
    grant_to_application(scope, "password_reset_tokens", ("SELECT", "INSERT", "UPDATE", "DELETE"))


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop the reset links."""
    revoke_from_application(scope, "password_reset_tokens")
    op.drop_table("password_reset_tokens")
