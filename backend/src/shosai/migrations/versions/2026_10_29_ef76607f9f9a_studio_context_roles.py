"""Where a person's own words go (studio; ADR 0074 ST-D2 as amended by the owner on 2026-10-29).

A person's "About you" goes to every Studio role or to the roles they name. `all_roles` keeps
"every role", so a role added later takes the words with no row rewritten; `roles` names the
roles otherwise, known roles only, and is empty while `all_roles` holds. Every earlier row
reads as every role: the columns come with their defaults.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from shosai.core.db.migration_scope import EVERY_HOME, MigrationScope, runs_in

revision: str = "ef76607f9f9a"
down_revision: str | None = "4b32f8e17344"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME

PROMPT_ROLES = "'live_answers', 'screenshots', 'code', 'system_design', 'notes'"


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Add the choice and its rules."""
    del scope
    op.add_column(
        "user_contexts",
        sa.Column("all_roles", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    op.add_column(
        "user_contexts",
        sa.Column("roles", postgresql.ARRAY(sa.Text()), server_default="{}", nullable=False),
    )
    op.create_check_constraint(
        op.f("ck_user_contexts_known_roles"),
        "user_contexts",
        f"roles <@ ARRAY[{PROMPT_ROLES}]::text[]",
    )
    op.create_check_constraint(
        op.f("ck_user_contexts_roles_or_all"),
        "user_contexts",
        "NOT all_roles OR cardinality(roles) = 0",
    )


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop them."""
    del scope
    op.drop_constraint(op.f("ck_user_contexts_roles_or_all"), "user_contexts", type_="check")
    op.drop_constraint(op.f("ck_user_contexts_known_roles"), "user_contexts", type_="check")
    op.drop_column("user_contexts", "roles")
    op.drop_column("user_contexts", "all_roles")
