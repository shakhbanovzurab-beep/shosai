"""The effect-key ledger: one applied effect per key, with its outcome (F1 audit A9)."""

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

revision: str = "72310e0e62f3"
down_revision: str | None = "959dbda6a28e"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Create the effect keys and open them to the application role."""
    op.create_table(
        "effect_keys",
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("fingerprint", sa.Text(), nullable=True),
        sa.Column("outcome", postgresql.JSONB(), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("org_id", sa.Uuid(), nullable=True),
        sa.Column(
            "recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "scope ~ '^[a-z][a-z0-9_]*(\\.[a-z][a-z0-9_]*)+$' AND length(scope) <= 64",
            name=op.f("ck_effect_keys_scope_format"),
        ),
        sa.CheckConstraint("length(key) BETWEEN 1 AND 200", name=op.f("ck_effect_keys_key_length")),
        sa.CheckConstraint(
            "fingerprint ~ '^[0-9a-f]{64}$'", name=op.f("ck_effect_keys_fingerprint_sha256")
        ),
        sa.CheckConstraint(
            "pg_column_size(outcome) <= 8192", name=op.f("ck_effect_keys_outcome_size")
        ),
        sa.CheckConstraint(
            "expires_at > recorded_at", name=op.f("ck_effect_keys_expires_after_recorded")
        ),
        sa.PrimaryKeyConstraint("scope", "key", name=op.f("pk_effect_keys")),
    )
    op.create_index("ix_effect_keys_expires_at", "effect_keys", ["expires_at"])
    grant_to_application(scope, "effect_keys", ("SELECT", "INSERT", "UPDATE", "DELETE"))


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop the effect keys."""
    revoke_from_application(scope, "effect_keys")
    op.drop_table("effect_keys")
