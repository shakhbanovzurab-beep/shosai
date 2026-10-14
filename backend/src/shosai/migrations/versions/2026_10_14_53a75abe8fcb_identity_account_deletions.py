"""Deletion requests and the erasure journal, in every home (identity step 7a).

The consent journal is append-only for the application, except for the erasure of an
account, so the application role may now delete from it too.
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

revision: str = "53a75abe8fcb"
down_revision: str | None = "dcbe089810b4"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Create the deletions; the saga deletes its row when the account is erased."""
    op.create_table(
        "account_deletions",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("erase_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "erased_owners",
            postgresql.ARRAY(sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.CheckConstraint(
            "state IN ('scheduled', 'cancelled', 'erasing')",
            name=op.f("ck_account_deletions_state_known"),
        ),
        sa.CheckConstraint(
            "erase_at > requested_at", name=op.f("ck_account_deletions_erase_after_request")
        ),
        sa.CheckConstraint(
            "(state = 'cancelled') = (cancelled_at IS NOT NULL)",
            name=op.f("ck_account_deletions_cancelled"),
        ),
        sa.CheckConstraint(
            "(state = 'erasing') = (started_at IS NOT NULL)",
            name=op.f("ck_account_deletions_started"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_account_deletions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_account_deletions")),
    )
    op.create_index(
        "ix_account_deletions_due",
        "account_deletions",
        ["run_at", "user_id"],
        postgresql_where=sa.text("state IN ('scheduled', 'erasing')"),
    )
    grant_to_application(scope, "account_deletions", ("SELECT", "INSERT", "UPDATE", "DELETE"))
    grant_to_application(scope, "user_consents", ("DELETE",))


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop the deletions; the consent journal is append-only again."""
    revoke_from_application(scope, "user_consents")
    grant_to_application(scope, "user_consents", ("SELECT", "INSERT"))
    revoke_from_application(scope, "account_deletions")
    op.drop_table("account_deletions")
