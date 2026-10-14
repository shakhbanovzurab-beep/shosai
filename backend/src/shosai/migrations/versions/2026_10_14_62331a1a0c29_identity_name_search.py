"""Trigram indexes for the operators' search by name, in every home (identity step 8b).

`pg_trgm` is a trusted extension, so the migration role creates it; the indexes serve
`ILIKE '%…%'` on the full and the display name.
"""

from alembic import op

from shosai.core.db.migration_scope import EVERY_HOME, MigrationScope, runs_in

revision: str = "62331a1a0c29"
down_revision: str | None = "96f93168bdec"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME

NAME_INDEXES = (
    ("ix_users_full_name_trgm", "full_name"),
    ("ix_users_display_name_trgm", "display_name"),
)


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Create the extension and one trigram index per name."""
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    for name, column in NAME_INDEXES:
        op.create_index(
            name,
            "users",
            [column],
            postgresql_using="gin",
            postgresql_ops={column: "gin_trgm_ops"},
        )


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop the indexes and the extension."""
    for name, _ in NAME_INDEXES:
        op.drop_index(name, table_name="users")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
