"""Social accounts linked to people, in every home (identity step 5).

A provider's user id is linked to one account; an account has at most one link per
provider. No provider token is stored.
"""

import sqlalchemy as sa
from alembic import op

from shosai.core.db.migration_scope import (
    EVERY_HOME,
    MigrationScope,
    grant_to_application,
    revoke_from_application,
    runs_in,
)

revision: str = "9f7ebc9fb893"
down_revision: str | None = "891568940e46"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Create the links; a person can remove a link, so DELETE too."""
    op.create_table(
        "user_identities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("email_verified_by_provider", sa.Boolean(), nullable=False),
        sa.Column(
            "linked_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "last_used_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "provider IN ('yandex', 'vk', 'google', 'github')",
            name=op.f("ck_user_identities_provider_known"),
        ),
        sa.CheckConstraint(
            "length(subject) BETWEEN 1 AND 256", name=op.f("ck_user_identities_subject_length")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_identities_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_identities")),
    )
    op.create_index(
        "uq_user_identities_subject", "user_identities", ["provider", "subject"], unique=True
    )
    op.create_index(
        "uq_user_identities_user", "user_identities", ["user_id", "provider"], unique=True
    )
    grant_to_application(scope, "user_identities", ("SELECT", "INSERT", "UPDATE", "DELETE"))


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop the links."""
    revoke_from_application(scope, "user_identities")
    op.drop_table("user_identities")
