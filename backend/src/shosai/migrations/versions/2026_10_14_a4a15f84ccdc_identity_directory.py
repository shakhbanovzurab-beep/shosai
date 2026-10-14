"""The directory of addresses, in the EU home only (§6, identity step 2).

The row holds the HMAC of the address, the account id, its home and its state: nothing
that names the person (nfr-4). The primary key on the HMAC makes the first confirmed
registration of an address win across both homes (inv-1).
"""

import sqlalchemy as sa
from alembic import op

from shosai.core.db.migration_scope import (
    MigrationScope,
    grant_to_application,
    revoke_from_application,
    runs_in,
)
from shosai.core.kernel.homes import Home

revision: str = "a4a15f84ccdc"
down_revision: str | None = "e8a142594282"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = (Home.EU,)

DIRECTORY_STATES = (
    "'claimed', 'active', 'frozen', 'banned', 'deletion_scheduled', 'transferring', 'deleted'"
)


def check(sql: str, name: str) -> sa.CheckConstraint:
    """A check constraint of the directory named by the project's convention."""
    return sa.CheckConstraint(sql, name=op.f(f"ck_directory_entries_{name}"))


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Create the directory; rows are claimed, updated and, 30 days after erasure, deleted."""
    op.create_table(
        "directory_entries",
        sa.Column("email_hmac", sa.LargeBinary(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("home", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        check(f"state IN ({DIRECTORY_STATES})", "state_known"),
        check("home IN ('ru', 'eu')", "home_known"),
        check("length(email_hmac) = 32", "email_hmac_length"),
        check("version >= 1", "version_positive"),
        sa.PrimaryKeyConstraint("email_hmac", name=op.f("pk_directory_entries")),
    )
    op.create_index("uq_directory_entries_user", "directory_entries", ["user_id"], unique=True)
    op.create_index(
        "ix_directory_entries_claimed",
        "directory_entries",
        ["updated_at"],
        postgresql_where=sa.text("state = 'claimed'"),
    )
    grant_to_application(scope, "directory_entries", ("SELECT", "INSERT", "UPDATE", "DELETE"))


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop the directory."""
    revoke_from_application(scope, "directory_entries")
    op.drop_table("directory_entries")
